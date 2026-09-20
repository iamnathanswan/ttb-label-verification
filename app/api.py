"""HTTP surface.

Nothing here touches disk or a database: uploads live in memory for the duration
of the request and are discarded when it ends (OPS-01).

Both documents are uploaded and both are extracted. An agent supplies a label and
the COLA application it belongs to; nothing is retyped, which is the point of the
feature — the interviews describe agents drowning in data entry verification, and
a tool that asks them to type the application values would be adding to that.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.batch import LabelUpload, stream_batch, verify_one
from app.config import settings
from app.extract_application import NotAnApplication, read_form_fields
from app.ingest import UnsupportedUpload, prepare
from app.limits import enforce
from app.models import ApplicationFields, VerificationResult
from app.pairing import Candidate, pair
from app.providers.base import ExtractionError, ExtractionProvider

router = APIRouter(prefix="/api")


class UploadTooLarge(Exception):
    """One file exceeds the per-file ceiling. Carries a message for the agent."""


async def _read(upload: UploadFile) -> bytes:
    content = await upload.read()
    if len(content) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise UploadTooLarge(f"{upload.filename} is larger than the {mb} MB limit. Upload a smaller file.")
    return content


async def _extract_application(content: bytes, filename: str, provider: ExtractionProvider) -> ApplicationFields:
    """Read an application, exactly where possible and by sight where not.

    A form completed digitally carries its values in AcroForm widgets and is read
    without a model. One that was printed and scanned has to be looked at, and the
    result says which happened so an agent can weigh it.
    """
    fields = await asyncio.to_thread(read_form_fields, content)
    if fields is not None:
        fields.filename = filename
        return fields

    image, media_type = await asyncio.to_thread(prepare, content)
    fields = await provider.extract_application(image, media_type)
    fields.extraction_source = "vision"
    fields.filename = filename
    return fields


@router.post("/verify", response_model=VerificationResult)
async def verify_label(
    request: Request,
    file: Annotated[UploadFile, File(description="Label image or PDF")],
    application: Annotated[UploadFile | None, File(description="COLA application, TTB F 5100.31 (PDF)")] = None,
) -> VerificationResult:
    """Verify one label, optionally against its application."""
    enforce(request, cost=1)

    try:
        content = await _read(file)
    except UploadTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    fields = None
    pairing_info = None
    if application is not None:
        try:
            application_bytes = await _read(application)
        except UploadTooLarge as exc:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
        try:
            fields = await _extract_application(
                application_bytes,
                application.filename or "application.pdf",
                request.app.state.provider,
            )
        except (NotAnApplication, UnsupportedUpload) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        outcome = pair(
            [file.filename or "label"],
            [Candidate(application.filename or "application.pdf", fields)],
        )
        pairing_info = outcome.pairs[0].info

    upload = LabelUpload(
        filename=file.filename or "label",
        content=content,
        application=fields,
        pairing=pairing_info,
    )

    try:
        return await verify_one(request.app.state.provider, upload)
    except UnsupportedUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExtractionError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=exc.message) from exc


@router.post("/verify/batch")
async def verify_batch(
    request: Request,
    files: Annotated[list[UploadFile], File(description="Label images or PDFs")],
    applications: Annotated[list[UploadFile] | None, File(description="COLA applications (PDF)")] = None,
) -> StreamingResponse:
    """Verify many labels, streaming each result as it completes (BAT-01, PRF-02)."""
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"{len(files)} files submitted; the limit is {settings.max_batch_files} per batch. "
                "Split the submission."
            ),
        )
    enforce(request, cost=len(files))

    rejected: list[dict[str, str]] = []

    candidates: list[Candidate] = []
    for upload in applications or []:
        name = upload.filename or "application.pdf"
        try:
            content = await _read(upload)
            fields = await _extract_application(content, name, request.app.state.provider)
            candidates.append(Candidate(name, fields))
        except (UploadTooLarge, NotAnApplication, UnsupportedUpload, ExtractionError) as exc:
            rejected.append({"filename": name, "message": f"Application could not be read: {exc}"})

    # A file too large for the per-file ceiling becomes one rejected label, not a
    # rejected submission (BAT-04). The rate limit was already charged for the
    # whole batch, so aborting would spend the budget and return nothing.
    label_bytes: dict[str, bytes] = {}
    total_bytes = 0
    for index, upload in enumerate(files):
        name = upload.filename or f"label-{index + 1}"
        try:
            content = await _read(upload)
        except UploadTooLarge as exc:
            rejected.append({"filename": name, "message": str(exc)})
            continue

        total_bytes += len(content)
        if total_bytes > settings.max_batch_bytes:
            mb = settings.max_batch_bytes // (1024 * 1024)
            rejected.append(
                {
                    "filename": name,
                    "message": (
                        f"The submission exceeds {mb} MB in total, so this label and any after it "
                        "were not processed. Split the batch."
                    ),
                }
            )
            break
        label_bytes[name] = content

    outcome = pair(list(label_bytes), candidates)
    uploads = [
        LabelUpload(
            filename=item.label_filename,
            content=label_bytes[item.label_filename],
            application=item.application.fields if item.application else None,
            pairing=item.info,
        )
        for item in outcome.pairs
    ]

    for unused in outcome.unused_applications:
        rejected.append(
            {
                "filename": unused.filename,
                "message": "No label matched this application, so it was not compared.",
            }
        )

    return StreamingResponse(
        stream_batch(request.app.state.provider, uploads, rejected=rejected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/config")
async def config() -> dict:
    """Limits the interface needs to know about before it lets someone upload."""
    return {
        "max_upload_bytes": settings.max_upload_bytes,
        "max_batch_files": settings.max_batch_files,
        "max_image_edge_px": settings.max_image_edge_px,
    }

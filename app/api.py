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

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
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

PREVIEW_EDGE_PX = 480
# Beyond a handful, thumbnails stop helping and start costing an upload each. A
# peak-season batch is reviewed through its results, not its input.
PREVIEW_LIMIT = 6


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

    # Start the application read before the label read so the two overlap. A
    # scanned form needs its own model call; run one after the other a pair cost
    # 7.8 s against a 5 s budget, and the label's own timer hid it by measuring
    # only its half.
    application_task = None
    application_name = (application.filename or "application.pdf") if application else None
    if application is not None:
        try:
            application_bytes = await _read(application)
        except UploadTooLarge as exc:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
        application_task = asyncio.create_task(
            _extract_application(application_bytes, application_name, request.app.state.provider)
        )

    upload = LabelUpload(filename=file.filename or "label", content=content)

    try:
        result = await verify_one(request.app.state.provider, upload, application_task=application_task)
    except (UnsupportedUpload, NotAnApplication) as exc:
        if application_task is not None:
            application_task.cancel()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExtractionError as exc:
        if application_task is not None:
            application_task.cancel()
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=exc.message) from exc

    if result.application is not None:
        outcome = pair([upload.filename], [Candidate(application_name, result.application)])
        result.pairing = outcome.pairs[0].info
    return result


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

    async def read_application(upload: UploadFile) -> Candidate | dict[str, str]:
        name = upload.filename or "application.pdf"
        try:
            content = await _read(upload)
            fields = await _extract_application(content, name, request.app.state.provider)
            return Candidate(name, fields)
        except (UploadTooLarge, NotAnApplication, UnsupportedUpload, ExtractionError) as exc:
            return {"filename": name, "message": f"Application could not be read: {exc}"}

    # Concurrently: a batch of scanned forms would otherwise read one at a time
    # before any label is touched.
    candidates: list[Candidate] = []
    for outcome_item in await asyncio.gather(*(read_application(u) for u in (applications or []))):
        (candidates if isinstance(outcome_item, Candidate) else rejected).append(outcome_item)

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


@router.post("/preview")
async def preview(
    request: Request,
    file: Annotated[UploadFile, File(description="Document to render a thumbnail of")],
) -> Response:
    """Render the first page of a document as a small PNG.

    So an agent can see what they dropped before spending a check on it. A browser
    can show an image on its own, but not a PDF without a viewer or a library, and
    the server already rasterises PDFs on the ingest path.

    Deliberately outside the extraction rate limit: this costs a little CPU and no
    inference, and counting it would let looking at your own documents exhaust the
    budget for checking them. The upload cap still applies.
    """
    try:
        content = await _read(file)
    except UploadTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    try:
        image, _ = await asyncio.to_thread(prepare, content, max_edge=PREVIEW_EDGE_PX)
    except UnsupportedUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(
        content=image,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/config")
async def config() -> dict:
    """Limits the interface needs to know about before it lets someone upload."""
    return {
        "max_upload_bytes": settings.max_upload_bytes,
        "max_batch_files": settings.max_batch_files,
        "max_image_edge_px": settings.max_image_edge_px,
        "preview_limit": PREVIEW_LIMIT,
    }

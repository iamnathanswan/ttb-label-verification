"""HTTP surface.

Nothing here touches disk or a database: uploads live in memory for the duration
of the request and are discarded when it ends (OPS-01).
"""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.batch import LabelUpload, stream_batch, verify_one
from app.config import settings
from app.ingest import UnsupportedUpload
from app.limits import enforce
from app.models import ExpectedValues, VerificationResult
from app.providers.base import ExtractionError

router = APIRouter(prefix="/api")


def _expected(**raw: object) -> ExpectedValues | None:
    """Build application values, or None when the agent supplied none (MCH-06).

    Field names follow TTB F 5100.31; see `ExpectedValues` for why class/type and
    country of origin are not among them.
    """
    cleaned = {k: (v or None) for k, v in raw.items()}
    values = ExpectedValues(**cleaned)
    return values if values.model_dump(exclude_none=True) else None


class UploadTooLarge(Exception):
    """One file exceeds the per-file ceiling. Carries a message for the agent."""


async def _read(upload: UploadFile) -> bytes:
    content = await upload.read()
    if len(content) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise UploadTooLarge(f"{upload.filename} is larger than the {mb} MB limit. Upload a smaller image.")
    return content


@router.post("/verify", response_model=VerificationResult)
async def verify_label(
    request: Request,
    file: Annotated[UploadFile, File(description="Label image or PDF")],
    brand_name: Annotated[str | None, Form()] = None,
    fanciful_name: Annotated[str | None, Form()] = None,
    source_of_product: Annotated[str | None, Form()] = None,
    type_of_product: Annotated[str | None, Form()] = None,
    net_contents: Annotated[str | None, Form()] = None,
    alcohol_content_pct: Annotated[float | None, Form()] = None,
    producer_name: Annotated[str | None, Form()] = None,
) -> VerificationResult:
    """Verify one label. Application values are optional (MCH-06)."""
    enforce(request, cost=1)
    try:
        content = await _read(file)
    except UploadTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    upload = LabelUpload(
        filename=file.filename or "label",
        content=content,
        expected=_expected(
            brand_name=brand_name,
            fanciful_name=fanciful_name,
            source_of_product=source_of_product,
            type_of_product=type_of_product,
            net_contents=net_contents,
            alcohol_content_pct=alcohol_content_pct,
            producer_name=producer_name,
        ),
    )

    try:
        return await verify_one(request.app.state.provider, upload)
    except UnsupportedUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExtractionError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=exc.message) from exc


def _expected_from_csv(raw: bytes) -> dict[str, ExpectedValues]:
    """Map filename -> application values (BAT-05, MCH-01).

    Column names are matched case- and separator-insensitively so a spreadsheet
    exported as "Brand Name" or "brand_name" both work.
    """
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    mapping: dict[str, ExpectedValues] = {}

    def pick(row: dict, *names: str) -> str | None:
        for key, value in row.items():
            if key and key.strip().lower().replace(" ", "_") in names:
                return (value or "").strip() or None
        return None

    for row in rows:
        filename = pick(row, "filename", "file", "label", "image")
        if not filename:
            continue
        abv = pick(row, "alcohol_content_pct", "abv", "alcohol_content")
        try:
            abv_value = float(abv) if abv else None
        except ValueError:
            abv_value = None
        source = (pick(row, "source_of_product", "source") or "").lower() or None
        product_type = (pick(row, "type_of_product", "product_type") or "").lower() or None
        if product_type:
            product_type = {
                "wine": "wine",
                "distilled spirits": "distilled_spirits",
                "distilled_spirits": "distilled_spirits",
                "spirits": "distilled_spirits",
                "malt beverages": "malt_beverage",
                "malt beverage": "malt_beverage",
                "malt_beverage": "malt_beverage",
                "beer": "malt_beverage",
            }.get(product_type)

        mapping[filename] = ExpectedValues(
            brand_name=pick(row, "brand_name", "brand"),
            fanciful_name=pick(row, "fanciful_name", "fanciful"),
            source_of_product=source if source in {"domestic", "imported"} else None,
            type_of_product=product_type,
            net_contents=pick(row, "net_contents", "net_content", "volume"),
            alcohol_content_pct=abv_value,
            producer_name=pick(row, "producer_name", "producer", "bottler"),
        )
    return mapping


@router.post("/verify/batch")
async def verify_batch(
    request: Request,
    files: Annotated[list[UploadFile], File(description="Label images or PDFs")],
    expected_csv: Annotated[UploadFile | None, File(description="Optional application values")] = None,
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

    expected_map: dict[str, ExpectedValues] = {}
    if expected_csv:
        try:
            expected_map = _expected_from_csv(await _read(expected_csv))
        except UploadTooLarge as exc:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    # A file too large for the per-file ceiling becomes one rejected label, not a
    # rejected submission: an agent who uploaded 300 labels and included one
    # 11 MB scan should get 299 results and one clear error (BAT-04). Their rate
    # limit was already charged for the whole batch, so aborting would spend the
    # budget and return nothing.
    uploads: list[LabelUpload] = []
    rejected: list[dict[str, str]] = []
    total_bytes = 0

    for index, upload_file in enumerate(files):
        name = upload_file.filename or f"label-{index + 1}"
        try:
            content = await _read(upload_file)
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

        uploads.append(LabelUpload(filename=name, content=content, expected=expected_map.get(name)))

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

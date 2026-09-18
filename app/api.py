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


def _expected(
    brand_name: str | None,
    class_type: str | None,
    alcohol_content_pct: float | None,
    net_contents: str | None,
    producer_name: str | None,
    country_of_origin: str | None,
) -> ExpectedValues | None:
    """Build application values, or None when the agent supplied none (MCH-06)."""
    values = ExpectedValues(
        brand_name=brand_name or None,
        class_type=class_type or None,
        alcohol_content_pct=alcohol_content_pct,
        net_contents=net_contents or None,
        producer_name=producer_name or None,
        country_of_origin=country_of_origin or None,
    )
    return values if values.model_dump(exclude_none=True) else None


async def _read(upload: UploadFile) -> bytes:
    content = await upload.read()
    if len(content) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"{upload.filename} is larger than the {mb} MB limit. Upload a smaller image.",
        )
    return content


@router.post("/verify", response_model=VerificationResult)
async def verify_label(
    request: Request,
    file: Annotated[UploadFile, File(description="Label image or PDF")],
    brand_name: Annotated[str | None, Form()] = None,
    class_type: Annotated[str | None, Form()] = None,
    alcohol_content_pct: Annotated[float | None, Form()] = None,
    net_contents: Annotated[str | None, Form()] = None,
    producer_name: Annotated[str | None, Form()] = None,
    country_of_origin: Annotated[str | None, Form()] = None,
) -> VerificationResult:
    """Verify one label. Application values are optional (MCH-06)."""
    enforce(request, cost=1)
    content = await _read(file)

    upload = LabelUpload(
        filename=file.filename or "label",
        content=content,
        expected=_expected(
            brand_name, class_type, alcohol_content_pct, net_contents, producer_name, country_of_origin
        ),
    )

    try:
        return await verify_one(request.app.state.provider, upload)
    except UnsupportedUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExtractionError as exc:
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
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
        mapping[filename] = ExpectedValues(
            brand_name=pick(row, "brand_name", "brand"),
            class_type=pick(row, "class_type", "class", "type"),
            alcohol_content_pct=abv_value,
            net_contents=pick(row, "net_contents", "net_content", "volume"),
            producer_name=pick(row, "producer_name", "producer", "bottler"),
            country_of_origin=pick(row, "country_of_origin", "country"),
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

    expected_map = _expected_from_csv(await expected_csv.read()) if expected_csv else {}

    uploads = [
        LabelUpload(
            filename=f.filename or f"label-{i + 1}",
            content=await _read(f),
            expected=expected_map.get(f.filename or ""),
        )
        for i, f in enumerate(files)
    ]

    return StreamingResponse(
        stream_batch(request.app.state.provider, uploads),
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

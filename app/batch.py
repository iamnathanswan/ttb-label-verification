"""Batch fan-out with bounded concurrency (BAT-01..06, PRF-02).

Sarah's importers submit 200-300 labels at once. Processing them sequentially at
~4 s each is 20 minutes of staring at a spinner, so labels are processed
concurrently and each result is streamed the moment it lands: the first card
appears inside the single-label budget and an agent starts working immediately
(PRF-02).

Concurrency is bounded because an unbounded fan-out of 300 simultaneous requests
earns a rate-limit rejection rather than throughput.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.config import settings
from app.ingest import UnsupportedUpload, prepare
from app.models import ExpectedValues, VerificationResult
from app.providers.base import ExtractionError, ExtractionProvider
from app.rules.engine import verify


@dataclass(slots=True)
class LabelUpload:
    filename: str
    content: bytes
    expected: ExpectedValues | None = None


async def verify_one(provider: ExtractionProvider, upload: LabelUpload) -> VerificationResult:
    """Ingest, extract, and apply the rules to a single label."""
    started = time.perf_counter()
    # prepare() is CPU-bound — PDF rasterisation, Pillow decode, LANCZOS resize,
    # JPEG re-encode. Run inline it would occupy the event loop and stall the
    # flush of results that have already completed, which is precisely what
    # PRF-02 depends on.
    image, media_type = await asyncio.to_thread(prepare, upload.content)
    fields, usage = await provider.extract(image, media_type)
    return verify(
        fields,
        upload.expected,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        filename=upload.filename,
        usage=usage,
    )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def stream_batch(
    provider: ExtractionProvider,
    uploads: list[LabelUpload],
    rejected: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    """Yield server-sent events as each label completes.

    One label failing must never abort the batch (BAT-04): an agent who uploaded
    300 labels should get 299 results and one clearly-marked error, not nothing.
    """
    rejected = rejected or []
    semaphore = asyncio.Semaphore(settings.extraction_concurrency)
    started = time.perf_counter()
    total = len(uploads) + len(rejected)

    yield _sse("start", {"total": total, "concurrency": settings.extraction_concurrency})

    # Files refused before processing are reported in the same stream, so the
    # interface has one place to look and nothing vanishes silently.
    completed_rejected = 0
    for failure in rejected:
        completed_rejected += 1
        yield _sse("error", {**failure, "progress": {"completed": completed_rejected, "total": total}})

    async def run(upload: LabelUpload) -> tuple[str, dict]:
        async with semaphore:
            try:
                result = await verify_one(provider, upload)
                return "result", result.model_dump(mode="json")
            except (UnsupportedUpload, ExtractionError) as exc:
                return "error", {"filename": upload.filename, "message": str(exc)}
            except Exception as exc:  # noqa: BLE001 — one bad label must not end the batch
                return "error", {
                    "filename": upload.filename,
                    "message": f"Unexpected failure while processing this label: {exc}",
                }

    tasks = [asyncio.create_task(run(u)) for u in uploads]
    completed = completed_rejected
    try:
        for coro in asyncio.as_completed(tasks):
            event, payload = await coro
            completed += 1
            payload["progress"] = {"completed": completed, "total": total}
            yield _sse(event, payload)
    finally:
        for task in tasks:
            task.cancel()

    yield _sse(
        "done",
        {
            "total": total,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        },
    )

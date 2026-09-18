"""Batch load characteristics — BAT-01, BAT-02, BAT-03, BAT-04, BAT-06, PRF-02, OPS-01, OPS-05.

Runs against StubProvider, so this exercises the system properties that matter at
scale — concurrency ceiling, per-label isolation, memory behaviour, no task leaks
— without spending API credit or taking three minutes. Real-API behaviour at
scale is measured separately by `scripts/verify_corpus.py`.
"""

import asyncio
import json
import tracemalloc

import pytest
from fastapi.testclient import TestClient

from app.batch import LabelUpload, stream_batch
from app.config import settings
from app.main import app
from app.models import LabelFields
from app.providers.base import ExtractionError, ExtractionProvider
from app.rules import constants as C

PEAK_BATCH = 300  # Sarah: "big importers who dump 200, 300 label applications on us at once"


def compliant() -> LabelFields:
    return LabelFields(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content_pct=45.0,
        net_contents_raw="750 mL",
        producer_name="OLD TOM DISTILLERY",
        producer_function_phrase="BOTTLED BY",
        warning_text=C.WARNING_STATEMENT,
        warning_heading_is_caps="yes",
        warning_heading_is_bold="yes",
        warning_body_is_bold="no",
        warning_visually_separated="yes",
        warning_on_contrasting_background="yes",
        same_field_of_vision="yes",
        beverage_type="distilled_spirits",
    )


class CountingProvider(ExtractionProvider):
    """Records peak simultaneous extractions so the ceiling can be asserted."""

    def __init__(self, delay: float = 0.005, fail_every: int = 0):
        self.in_flight = 0
        self.peak = 0
        self.calls = 0
        self._delay = delay
        self._fail_every = fail_every

    async def extract(self, image_bytes: bytes, media_type: str):
        self.calls += 1
        call = self.calls
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self._delay)
            if self._fail_every and call % self._fail_every == 0:
                raise ExtractionError("synthetic failure", retryable=True)
            return compliant(), {"input_tokens": 0, "output_tokens": 0}
        finally:
            self.in_flight -= 1


def uploads(count: int, image: bytes) -> list[LabelUpload]:
    return [LabelUpload(filename=f"label-{i:03d}.png", content=image) for i in range(count)]


@pytest.fixture
def image() -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "labels" / "compliant_bourbon.png").read_bytes()


async def collect(provider, batch):
    events = []
    async for chunk in stream_batch(provider, batch):
        for block in chunk.strip().split("\n\n"):
            lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
            if "event" in lines:
                events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.mark.asyncio
async def test_peak_batch_returns_every_label(image):
    """BAT-02 — a peak-season dump must come back whole."""
    provider = CountingProvider()
    events = await collect(provider, uploads(PEAK_BATCH, image))

    results = [p for name, p in events if name == "result"]
    assert len(results) == PEAK_BATCH
    assert events[0][0] == "start" and events[-1][0] == "done"
    assert events[-1][1]["total"] == PEAK_BATCH


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_the_configured_ceiling(image):
    """BAT-06 — an unbounded fan-out of 300 requests earns a rate-limit rejection."""
    provider = CountingProvider()
    await collect(provider, uploads(PEAK_BATCH, image))
    assert provider.peak <= settings.extraction_concurrency
    assert provider.peak > 1, "no concurrency at all would be a regression"


@pytest.mark.asyncio
async def test_progress_counts_every_label_exactly_once(image):
    events = await collect(CountingProvider(), uploads(50, image))
    completed = [p["progress"]["completed"] for n, p in events if n in {"result", "error"}]
    assert sorted(completed) == list(range(1, 51))


@pytest.mark.asyncio
async def test_failures_do_not_abort_or_lose_the_rest(image):
    """BAT-04 — 299 results and a handful of clear errors beats nothing."""
    provider = CountingProvider(fail_every=10)
    events = await collect(provider, uploads(100, image))

    results = [p for n, p in events if n == "result"]
    errors = [p for n, p in events if n == "error"]
    assert len(errors) == 10
    assert len(results) == 90
    assert len(results) + len(errors) == 100


@pytest.mark.asyncio
async def test_memory_does_not_grow_with_batch_size(image):
    """Uploads are held in memory (OPS-01), so growth must track inputs, not results."""
    tracemalloc.start()
    baseline = tracemalloc.take_snapshot()
    await collect(CountingProvider(), uploads(200, image))
    after = tracemalloc.take_snapshot()
    grown = sum(s.size_diff for s in after.compare_to(baseline, "filename"))
    tracemalloc.stop()
    # 200 labels of accumulated result objects should stay well inside 100 MB.
    assert grown < 100 * 1024 * 1024, f"retained {grown / 1024 / 1024:.1f} MB after the batch"


def test_peak_batch_is_not_refused_by_the_rate_limit(image):
    """BAT-02 and OPS-05 must not contradict each other.

    A ceiling that rejects the very batch size the tool advertises would fail on
    the first peak-season submission — the exact scenario it was built for.
    """
    with TestClient(app) as client:
        client.app.state.provider = CountingProvider()
        files = [("files", (f"l{i}.png", image, "image/png")) for i in range(PEAK_BATCH)]
        response = client.post("/api/verify/batch", files=files)
    assert response.status_code == 200, response.json()


def test_misconfigured_limits_are_refused_at_startup():
    """A ceiling below the advertised batch size must fail loudly, not silently.

    This is the bug the peak-batch test caught: two limits written independently,
    contradicting each other on the exact workload the tool exists for.
    """
    from app.config import Settings

    with pytest.raises(ValueError, match="below max_batch_files"):
        Settings(max_batch_files=300, rate_limit_labels=120)


def test_rate_limit_defaults_above_the_advertised_batch_size():
    from app.config import Settings

    s = Settings(max_batch_files=250)
    assert s.rate_limit_labels >= 250


def test_decompression_bomb_is_refused_before_decoding():
    """A small file that expands to an enormous raster must not reach the decoder.

    136 KB of PNG can decode to 144 megapixels. Pillow warns but does not block,
    and at the configured concurrency that is enough to exhaust the container.
    """
    import io as _io

    from PIL import Image

    from app.ingest import UnsupportedUpload, prepare

    buf = _io.BytesIO()
    Image.new("L", (12000, 12000), 128).save(buf, format="PNG", optimize=True)
    payload = buf.getvalue()
    assert len(payload) < 1024 * 1024, "the point is that it is a small file"

    with pytest.raises(UnsupportedUpload, match="too large to process"):
        prepare(payload)


def test_realistic_photograph_is_still_accepted():
    """The ceiling must not reject a normal phone photograph of a bottle."""
    import io as _io

    from PIL import Image

    from app.ingest import prepare

    buf = _io.BytesIO()
    Image.new("RGB", (6000, 4000), "white").save(buf, format="JPEG", quality=80)
    image, media_type = prepare(buf.getvalue())
    assert media_type == "image/jpeg" and image

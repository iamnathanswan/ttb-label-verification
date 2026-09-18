"""Measure extraction latency against PRF-01 (~5 s per label); reports PRF-03 timings.

PRF-01 is a binding requirement and the README publishes measured numbers, so
this script is the source of those figures rather than a one-off.

Usage: python scripts/benchmark.py [runs]
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path

from app.ingest import prepare
from app.providers.anthropic_provider import AnthropicProvider

LABEL = Path(__file__).parent.parent / "tests" / "fixtures" / "labels" / "compliant_bourbon.png"
BUDGET_MS = 5000


async def main(runs: int) -> int:
    raw = LABEL.read_bytes()
    t0 = time.perf_counter()
    image, media = prepare(raw)
    print(f"ingest  {len(raw) // 1024} KB -> {len(image) // 1024} KB in {(time.perf_counter() - t0) * 1000:.0f} ms\n")

    provider = AnthropicProvider()
    timings: list[float] = []
    first = None

    try:
        for i in range(runs):
            t = time.perf_counter()
            fields, usage = await provider.extract(image, media)
            elapsed = (time.perf_counter() - t) * 1000
            timings.append(elapsed)
            first = first or fields
            print(
                f"run {i + 1}  {elapsed:7.0f} ms   in={usage['input_tokens']:5d} "
                f"out={usage['output_tokens']:4d} cache_read={usage['cache_read_input_tokens']:5d}",
                flush=True,
            )
    finally:
        await provider.aclose()

    ordered = sorted(timings)
    p50 = statistics.median(ordered)
    # Nearest-rank p95; with few samples this is simply the slowest run.
    p95 = ordered[min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))]
    over = sum(1 for x in timings if x > BUDGET_MS)
    print(
        f"\nn={len(timings)}  p50 {p50:.0f} ms  p95 {p95:.0f} ms  "
        f"min {ordered[0]:.0f}  max {ordered[-1]:.0f}  budget {BUDGET_MS}"
    )
    print(f"over budget: {over}/{len(timings)} runs")
    print("PRF-01 (p50):", "PASS" if p50 <= BUDGET_MS else "FAIL")
    print("PRF-01 (p95):", "PASS" if p95 <= BUDGET_MS else "FAIL")

    if first:
        print("\nextracted:")
        for name in (
            "brand_name", "class_type", "alcohol_content_pct", "alcohol_content_proof",
            "net_contents_raw", "producer_function_phrase", "producer_name", "beverage_type",
            "warning_heading_is_caps", "warning_heading_is_bold", "warning_body_is_bold",
            "warning_visually_separated", "same_field_of_vision",
        ):
            print(f"  {name:34s} {getattr(first, name)!r}")
        print(f"\n  warning_text: {first.warning_text!r}")

    return 0 if p50 <= BUDGET_MS else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)))

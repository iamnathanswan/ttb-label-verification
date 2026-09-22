#!/usr/bin/env python3
"""Measure a real batch against the deployed service (BAT-01..06, PRF-02).

`tests/test_load.py` exercises the fan-out at the full 300 against StubProvider —
concurrency ceiling, per-label isolation, memory, no task leaks — without spending
API credit. That proves the machinery. It does not prove throughput, because the
stub returns instantly.

This spends real credit to measure what an agent would actually wait for. Cost is
printed before anything is sent, and --yes is required to proceed.

Usage:
  python scripts/batch_load.py --url $DEPLOYED --count 50 --yes
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

LABEL = Path(__file__).parent.parent / "tests" / "fixtures" / "labels" / "compliant_bourbon.png"
COST_PER_LABEL = 0.0121  # measured, docs/perf.md


async def run(url: str, count: int) -> dict:
    image = LABEL.read_bytes()
    files = [("files", (f"label_{i:03d}.png", image, "image/png")) for i in range(count)]

    first_result_at = None
    completions: list[float] = []
    results = errors = 0
    started = time.perf_counter()

    timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=600.0)
    async with (
        httpx.AsyncClient(timeout=timeout) as client,
        client.stream("POST", f"{url}/api/verify/batch", files=files) as response,
    ):
        response.raise_for_status()
        event = None
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event in {"result", "error"}:
                now = time.perf_counter() - started
                if first_result_at is None:
                    first_result_at = now
                completions.append(now)
                if event == "result":
                    results += 1
                else:
                    errors += 1
                    payload = json.loads(line.split(":", 1)[1])
                    print(f"  error: {payload.get('filename')}: {payload.get('message')}")

    wall = time.perf_counter() - started
    # Gaps between consecutive completions approximate steady-state service time.
    gaps = [b - a for a, b in zip(completions, completions[1:], strict=False)]
    return {
        "count": count,
        "results": results,
        "errors": errors,
        "wall_s": wall,
        "first_result_s": first_result_at,
        "throughput_per_s": results / wall if wall else 0,
        "median_gap_ms": statistics.median(gaps) * 1000 if gaps else 0,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--yes", action="store_true", help="confirm the spend")
    args = p.parse_args()

    cost = args.count * COST_PER_LABEL
    print(f"{args.count} labels against {args.url} — approximately ${cost:.2f} of API credit")
    if not args.yes:
        print("Refusing to spend without --yes.")
        return 1

    m = asyncio.run(run(args.url, args.count))
    print(f"\n  labels            {m['count']}")
    print(f"  results / errors  {m['results']} / {m['errors']}")
    print(f"  first result      {m['first_result_s'] * 1000:,.0f} ms   (PRF-02: inside the 5,000 ms budget)")
    print(f"  wall clock        {m['wall_s']:,.1f} s")
    print(f"  throughput        {m['throughput_per_s']:.2f} labels/s")
    print(f"  steady-state gap  {m['median_gap_ms']:,.0f} ms between completions")
    print(f"  projected for 300 {300 / m['throughput_per_s'] / 60:.1f} min")
    return 0 if m["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

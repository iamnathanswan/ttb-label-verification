"""Run the fixture corpus end to end and compare against expected.json.

Unit tests prove each rule fires on synthetic input. This proves the whole chain
works on real images: extraction reads the defect, and the rule catches it.

Usage: python scripts/verify_corpus.py
"""

import asyncio
import json
import sys
from pathlib import Path

from app.ingest import prepare
from app.providers.anthropic_provider import AnthropicProvider
from app.rules.engine import verify

LABELS = Path(__file__).parent.parent / "tests" / "fixtures" / "labels"


async def main() -> int:
    manifest = json.loads((LABELS / "expected.json").read_text())
    provider = AnthropicProvider()
    failures = []

    try:
        for name, meta in manifest.items():
            fields, usage = await provider.extract(*prepare((LABELS / name).read_bytes()))
            result = verify(fields, elapsed_ms=usage.get("extract_ms", 0), filename=name)

            want_overall = meta.get("expect_overall")
            want_fail = set(meta.get("expect_fail", []))
            got_fail = {c.id for c in result.failures}

            overall_ok = want_overall is None or result.overall.value == want_overall
            rules_ok = want_fail <= got_fail
            ok = overall_ok and rules_ok

            mark = "ok  " if ok else "MISS"
            print(f"{mark} {name:32s} {result.overall.value:6s} "
                  f"(want {want_overall or '-':6s})  failed={sorted(got_fail) or '-'}", flush=True)
            if not ok:
                failures.append((name, want_overall, result.overall.value, sorted(want_fail - got_fail)))
    finally:
        await provider.aclose()

    print()
    if failures:
        print(f"{len(failures)} fixture(s) did not behave as documented:")
        for name, want, got, missed in failures:
            print(f"  {name}: expected {want}, got {got}" + (f"; rules not triggered: {missed}" if missed else ""))
        return 1

    print(f"all {len(manifest)} fixtures behaved as documented")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

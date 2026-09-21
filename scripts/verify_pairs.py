"""Check every label/application pair against a running service.

The label corpus proves the compliance rules fire on real images. This proves the
comparison does: each application fixture carries one deliberate disagreement
with the label it pairs to, and each must produce the outcome its manifest
documents.

Exits non-zero on any departure, so it can gate a release.

    python scripts/verify_pairs.py [--url https://...]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
LABELS = ROOT / "tests" / "fixtures" / "labels"
APPLICATIONS = ROOT / "tests" / "fixtures" / "applications"
DEFAULT_URL = "https://ttb-label-verification-production-a79a.up.railway.app"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    endpoint = args.url.rstrip("/") + "/api/verify"

    manifest = json.loads((APPLICATIONS / "expected.json").read_text())
    failures = 0

    with httpx.Client(timeout=180.0) as client:
        for name, meta in manifest.items():
            label = meta.get("pairs_with")
            if not label:
                print(f"     {name:42s} orphan — exercised by the batch pairing tests")
                continue

            started = time.perf_counter()
            response = client.post(
                endpoint,
                files={
                    "file": (label, (LABELS / label).read_bytes(), "image/png"),
                    "application": (name, (APPLICATIONS / name).read_bytes(), "application/pdf"),
                },
            )
            elapsed = (time.perf_counter() - started) * 1000

            if response.status_code != 200:
                print(f"MISS {name:42s} HTTP {response.status_code} {response.text[:60]}")
                failures += 1
                continue

            body = response.json()
            want = meta.get("expect_overall")
            ok = want is None or body["overall"] == want
            failures += not ok
            findings = [c["id"] for c in body["checks"] if c["status"] != "PASS" and not c["advisory"]]
            print(
                f"{'ok  ' if ok else 'MISS'} {name:42s} {body['overall']:6s} "
                f"(want {want or '-':6s}) {elapsed:6.0f}ms  "
                f"read={body['application']['extraction_source']:12s} "
                f"{', '.join(findings) or '—'}"
            )

    print()
    print("all pairs behaved as documented" if not failures else f"{failures} pair(s) did not")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

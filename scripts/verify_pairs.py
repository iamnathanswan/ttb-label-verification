"""Check every label/application pair against a running service.

The label corpus proves the compliance rules fire on real images. This proves the
comparison does: each application fixture carries one deliberate disagreement
with the label it pairs to, and each must produce the outcome its manifest
documents.

`--batch` answers a different question. Submitted one pair at a time, pairing
short-circuits on SOLE_PAIR and never consults a filename, so the single-pair run
below proves the comparison but nothing about matching. `--batch` sends every
label and every application in one request, shuffled, and checks each label
found its own — which is what happens when an importer sends three hundred at
once.

Exits non-zero on any departure, so it can gate a release.

    python scripts/verify_pairs.py [--url https://...] [--batch]
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


def verify_batch(url: str) -> int:
    """Send every pair at once and check that each label found its own application.

    Labels are renamed to carry their application's serial, which is how a COLA
    export arrives and the strategy pairing trusts most. The orphan application is
    included deliberately: it must be reported, never quietly attached to whichever
    label happened to be left over.
    """
    manifest = json.loads((APPLICATIONS / "expected.json").read_text())
    pairs = {name: meta["pairs_with"] for name, meta in manifest.items() if meta.get("pairs_with")}
    orphans = [name for name, meta in manifest.items() if not meta.get("pairs_with")]

    files = []
    expected: dict[str, str] = {}
    for application, label in pairs.items():
        serial = application.split("-application")[0]
        label_name = f"{serial}_label.png"
        expected[label_name] = application
        files.append(("files", (label_name, (LABELS / label).read_bytes(), "image/png")))
    # Reversed, so a pairing that only works when the lists line up would fail here.
    for application in reversed(list(pairs) + orphans):
        files.append(("applications", (application, (APPLICATIONS / application).read_bytes(), "application/pdf")))

    print(f"{len(expected)} labels and {len(pairs) + len(orphans)} applications in one batch, shuffled\n")

    started = time.perf_counter()
    with httpx.Client(timeout=600.0) as client:
        response = client.post(url + "/api/verify/batch", files=files)
    response.raise_for_status()
    elapsed = time.perf_counter() - started

    results, errors = [], []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if lines.get("event") == "result":
            results.append(json.loads(lines["data"]))
        elif lines.get("event") == "error":
            errors.append(json.loads(lines["data"]))

    failures = 0
    for label_name, want in sorted(expected.items()):
        found = next((r for r in results if r["filename"] == label_name), None)
        got = (found or {}).get("pairing", {}).get("application_filename")
        rule = (found or {}).get("pairing", {}).get("rule", "—")
        ok = got == want
        failures += not ok
        print(f"{'ok  ' if ok else 'MISS'} {label_name:22s} -> {str(got):44s} {rule}")

    for orphan in orphans:
        reported = any(orphan in json.dumps(e) for e in errors)
        failures += not reported
        print(f"{'ok  ' if reported else 'MISS'} {orphan:22s} -> reported as unpaired")

    print(f"\n{len(results)} results in {elapsed:.1f} s")
    print("every label paired to its own application" if not failures else f"{failures} pairing(s) wrong")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--batch", action="store_true", help="send every pair in one request")
    args = parser.parse_args()
    if args.batch:
        return verify_batch(args.url.rstrip("/"))
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

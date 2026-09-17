#!/usr/bin/env python3
"""Cross-check requirement IDs across the specification documents.

Expands range notation (EXT-01..08) so coverage is measured accurately rather
than by literal string match. Exits non-zero if any ID is referenced but not
defined, or defined-and-buildable but not covered by a task.

Usage: python3 docs/check_coverage.py   (from the repository root)
"""

import re
import sys
from pathlib import Path

ID = r"[A-Z]{3}-\d{2}"
DOCS = Path(__file__).parent


def expand(text: str) -> set[str]:
    """Collect requirement IDs, expanding `PRE-01..08` ranges."""
    ids = set(re.findall(rf"\b{ID}\b", text))
    for prefix, lo, hi in re.findall(r"\b([A-Z]{3})-(\d{2})\.\.(\d{2})\b", text):
        ids.update(f"{prefix}-{n:02d}" for n in range(int(lo), int(hi) + 1))
    return ids


def main() -> int:
    requirements = (DOCS / "requirements.md").read_text(encoding="utf-8")
    tasks = (DOCS / "tasks.md").read_text(encoding="utf-8")
    plan = (DOCS / "plan.md").read_text(encoding="utf-8")

    defined = set(re.findall(rf"^\| ({ID}) \|", requirements, re.M))
    buildable = {i for i in defined if not i.startswith("OOS")}
    referenced = expand(tasks) | expand(plan)

    phantom = sorted(referenced - defined)
    uncovered = sorted(buildable - expand(tasks))

    print(
        f"requirements defined : {len(defined)} "
        f"({len(buildable)} buildable, {len(defined) - len(buildable)} out-of-scope)"
    )
    print(f"covered by a task    : {len(buildable & expand(tasks))} / {len(buildable)}")
    print(f"phantom IDs          : {phantom or 'none'}")
    print(f"uncovered            : {uncovered or 'none'}")

    return 1 if (phantom or uncovered) else 0


if __name__ == "__main__":
    sys.exit(main())

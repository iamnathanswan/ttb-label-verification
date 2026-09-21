#!/usr/bin/env python3
"""Build a folder of ready-to-try label/application pairs.

The fixtures under tests/ exist to make tests fail in specific ways. These are
for a person: paired files with obvious names, and a README saying what each one
should do, so the tool can be exercised without reading any code.

Run: python scripts/make_samples.py
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

LABELS = ROOT / "tests" / "fixtures" / "labels"
APPS = ROOT / "tests" / "fixtures" / "applications"
OUT = ROOT / "samples"

# (folder, label fixture, application fixture, what it demonstrates)
PAIRS = [
    ("01-everything-matches", "compliant_bourbon.png", "24-0417-application.pdf",
     "A compliant label and the application that matches it. Expect PASS."),
    ("02-brand-case-differs", "compliant_bourbon.png", "24-0418-application-case-differs.pdf",
     "The application says “Old Tom Distillery”, the label says “OLD TOM DISTILLERY”. "
     "Expect NEEDS REVIEW, not a rejection — it is obviously the same brand."),
    ("03-wrong-brand", "compliant_bourbon.png", "24-0419-application-wrong-brand.pdf",
     "The application declares a different brand entirely. Expect FAILED."),
    ("04-declared-import-no-origin", "compliant_bourbon.png", "24-0420-application-imported.pdf",
     "The application declares an imported product but the label states no country of "
     "origin. Expect FAILED on 27 CFR 5.69 — the label alone gives no clue, so only "
     "the application catches this."),
    ("05-wrong-product-type", "compliant_bourbon.png", "24-0421-application-wine.pdf",
     "The application declares wine; the label is a bourbon. Expect NEEDS REVIEW, and "
     "note that distilled spirits rules are not applied to a product declared as wine."),
    ("06-scanned-application", "compliant_bourbon.png", "24-0422-application-scanned.pdf",
     "The same application printed and scanned, so it has no form fields left. Expect "
     "PASS, and the application to be badged “read by sight” instead of "
     "“read from form fields”."),
    ("07-warning-body-bold", "warning_body_bold.png", "24-0417-application.pdf",
     "The whole government warning is bold. 27 CFR 16.22(a)(2) bolds the heading and "
     "forbids bolding the rest. Expect FAILED — and note OCR cannot see this at all."),
    ("08-warning-title-case", "warning_title_case.png", "24-0417-application.pdf",
     "The warning heading reads “Government Warning:” instead of capitals. "
     "Expect FAILED, with the exact wording difference shown."),
    ("09-label-only", "compliant_bourbon.png", None,
     "No application at all. The regulation checks still run; the matching section is "
     "simply not checked."),
]


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    lines = [
        "# Sample documents",
        "",
        "Ready-made label and COLA application pairs for trying the tool. Each folder holds",
        "one label and, where relevant, the application it belongs to.",
        "",
        "Drop both files on the page together — or drop the whole folder.",
        "",
        "Applications are the real TTB F 5100.31 filled in programmatically; the blank form",
        "came from ttb.gov. Labels are synthetic, each built with one deliberate defect.",
        "",
        "| Folder | What it shows | Expect |",
        "|---|---|---|",
    ]

    expectations = {
        "01": "PASS", "02": "NEEDS REVIEW", "03": "FAILED", "04": "FAILED",
        "05": "NEEDS REVIEW", "06": "PASS", "07": "FAILED", "08": "FAILED", "09": "PASS",
    }

    for folder, label, application, note in PAIRS:
        target = OUT / folder
        target.mkdir()
        shutil.copy(LABELS / label, target / f"label-{label}")
        if application:
            shutil.copy(APPS / application, target / f"application-{application}")
        (target / "README.md").write_text(f"# {folder}\n\n{note}\n")
        lines.append(f"| `{folder}` | {note.split('.')[0]}. | {expectations[folder[:2]]} |")

    lines += [
        "",
        "## Making your own",
        "",
        "`tests/fixtures/generate_labels.py` draws labels and",
        "`tests/fixtures/generate_applications.py` fills applications. Both are small and",
        "commented; adding a case is a few lines in the table at the bottom of either file.",
        "",
        "The blank form is at `tests/fixtures/applications/_blank_form_ttb_f_5100_31.pdf` if",
        "you would rather fill one in by hand — it is a normal fillable PDF, and the tool",
        "reads whatever a PDF viewer saves.",
    ]

    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {len(PAIRS)} sample folders to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

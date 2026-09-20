#!/usr/bin/env python3
"""Fill the real TTB F 5100.31 to produce test applications.

Generating rather than mocking matters here: the reader resolves the source and
type checkboxes by position within a shared field name, which only a genuine form
exercises. A hand-built PDF would pass tests the real artifact would fail.

The blank form in this directory is the official one, downloaded from ttb.gov
(OMB No. 1513-0020).

Run: python tests/fixtures/generate_applications.py
"""

import json
from pathlib import Path

import pymupdf

HERE = Path(__file__).parent
BLANK = HERE / "applications" / "_blank_form_ttb_f_5100_31.pdf"
OUT = HERE / "applications"

from app.extract_application import (  # noqa: E402 — needs HERE on the path first
    FIELD_APPLICANT,
    FIELD_BRAND,
    FIELD_FANCIFUL,
    FIELD_PERMIT,
    GROUP_SOURCE,
    GROUP_TYPE,
    SOURCE_STATES,
    TYPE_STATES,
)


def fill(
    name: str,
    *,
    year="24",
    serial="0417",
    permit="DSP-KY-21034",
    brand="OLD TOM DISTILLERY",
    fanciful="",
    applicant="OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY 40004",
    source="domestic",
    product_type="distilled_spirits",
    flatten=False,
) -> None:
    doc = pymupdf.open(BLANK)

    text_values = {
        FIELD_BRAND: brand,
        FIELD_FANCIFUL: fanciful,
        FIELD_APPLICANT: applicant,
        FIELD_PERMIT: permit,
        "YEAR 1": year[0],
        "YEAR 2": year[1],
        **{f"SERIAL NUMBER {i + 1}": serial[i] for i in range(min(4, len(serial)))},
    }

    for page in doc:
        for widget in page.widgets():
            if widget.field_name in text_values:
                widget.field_value = text_values[widget.field_name]
                widget.update()

    # Radio groups are selected by export state, matching how the reader works.
    for page in doc:
        for group, states, wanted in (
            (GROUP_SOURCE, SOURCE_STATES, source),
            (GROUP_TYPE, TYPE_STATES, product_type),
        ):
            state = next((s for s, value in states.items() if value == wanted), None)
            if state is None:
                continue
            for widget in page.widgets():
                if widget.field_name == group and state in widget.button_states().get("normal", []):
                    widget.field_value = state
                    widget.update()

    if flatten:
        # A printed-and-scanned submission: no widgets, only pixels. Scans are
        # JPEG-compressed in practice; inserting lossless pixmaps produced a
        # 38 MB fixture that the upload limit rightly rejected, which would have
        # tested nothing except the limit.
        flat = pymupdf.open()
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            jpeg = pix.tobytes("jpeg", jpg_quality=70)
            new_page = flat.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(page.rect, stream=jpeg)
        flat.save(OUT / f"{name}.pdf", deflate=True, garbage=4)
    else:
        doc.save(OUT / f"{name}.pdf")


CASES = {
    "24-0417-application": (
        {},
        {"pairs_with": "compliant_bourbon.png", "note": "Matches the compliant bourbon label exactly. The clean path."},
    ),
    "24-0418-application-case-differs": (
        {"serial": "0418", "brand": "Old Tom Distillery"},
        {
            "pairs_with": "compliant_bourbon.png",
            "note": "Brand differs from the label only in capitalisation. Dave's case: REVIEW, not FAIL.",
        },
    ),
    "24-0419-application-wrong-brand": (
        {"serial": "0419", "brand": "YOUNG TOM DISTILLERY"},
        {"pairs_with": "compliant_bourbon.png", "note": "A genuinely different brand. FAIL."},
    ),
    "24-0420-application-imported": (
        {"serial": "0420", "source": "imported", "applicant": "ATLANTIC SPIRITS CO., NEWARK, NEW JERSEY 07102"},
        {
            "pairs_with": "compliant_bourbon.png",
            "note": "Declares an imported product; the label states no country of origin. VAL-13 fails "
            "on the declaration, which inference alone could never catch.",
        },
    ),
    "24-0421-application-wine": (
        {"serial": "0421", "product_type": "wine"},
        {
            "pairs_with": "compliant_bourbon.png",
            "note": "Declares wine against a distilled spirits label. Commodity mismatch surfaced, and "
            "Part 5 rules are not applied to a product the form says is wine.",
        },
    ),
    "24-0422-application-scanned": (
        {"serial": "0422", "flatten": True},
        {
            "pairs_with": "compliant_bourbon.png",
            "note": "Printed and scanned: no AcroForm widgets, so the vision fallback must read it.",
        },
    ),
    "24-0423-application-orphan": (
        {"serial": "0423", "brand": "NOBODY'S LABEL"},
        {"pairs_with": None, "note": "No matching label. Must be reported as unpaired, never guessed onto something."},
    ),
}

if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(HERE.parent.parent))
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (kwargs, meta) in CASES.items():
        fill(name, **kwargs)
        manifest[f"{name}.pdf"] = meta
    (OUT / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(CASES)} applications + expected.json to {OUT}")

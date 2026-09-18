#!/usr/bin/env python3
"""Generate the synthetic label corpus.

The assessment invites generated test labels. Generating rather than sourcing them
lets us author specific regulatory defects — a title-case warning heading, a
fully-bolded warning body, an ABV inside and outside the §5.65(c) tolerance — so
every rule can be proven to fire. Images are committed; this script is the record
of how they were made.

Run: python3 tests/fixtures/generate_labels.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "labels"

# 27 CFR 16.21, verbatim.
WARNING_HEAD = "GOVERNMENT WARNING:"
WARNING_BODY = (
    " (1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car "
    "or operate machinery, and may cause health problems."
)

MARKETING_BEFORE = (
    "Aged in charred new oak for a minimum of four summers in our rickhouse on the "
    "banks of the Salt River, where the temperature swing does the patient work."
)
MARKETING_AFTER = (
    "Best enjoyed neat or over a single large cube. Visit the distillery for tours "
    "daily except Sunday, and ask for the barrel-proof pour at the tasting bar."
)

FONTS = {
    "regular": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "bold": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "serif": "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "serif_bold": "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
}

W, H = 1000, 1400
CREAM, INK, GOLD = (247, 243, 233), (26, 26, 26), (138, 109, 46)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS[name], size)


def centre(d: ImageDraw.ImageDraw, y: int, text: str, f, fill=INK) -> int:
    w = d.textbbox((0, 0), text, font=f)[2]
    d.text(((W - w) // 2, y), text, font=f, fill=fill)
    return y + d.textbbox((0, 0), text, font=f)[3] + 8


def wrap(d, x, y, text, f, max_w, fill=INK, leading=6) -> int:
    words, line = text.split(), ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textbbox((0, 0), trial, font=f)[2] > max_w and line:
            d.text((x, y), line, font=f, fill=fill)
            y += d.textbbox((0, 0), line, font=f)[3] + leading
            line = word
        else:
            line = trial
    if line:
        d.text((x, y), line, font=f, fill=fill)
        y += d.textbbox((0, 0), line, font=f)[3] + leading
    return y


def draw_warning(d, y, *, heading: str, head_font: str, body_font: str, box: bool) -> int:  # noqa: D401
    """Lay out the warning. Defects are introduced by varying the arguments."""
    pad = 60
    if box:
        d.rectangle([pad - 14, y - 14, W - pad + 14, y + 190], outline=INK, width=2)
    hf, bf = font(head_font, 21), font(body_font, 20)
    hw = d.textbbox((0, 0), heading, font=hf)[2]
    d.text((pad, y), heading, font=hf, fill=INK)
    # Body continues on the heading's line, then wraps.
    first, rest = WARNING_BODY[:1], WARNING_BODY[1:]
    d.text((pad + hw, y), first, font=bf, fill=INK)
    return wrap(d, pad, y + 30, rest.strip(), bf, W - 2 * pad, leading=5)


def build(
    name: str,
    *,
    brand="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    abv_text="45% Alc./Vol. (90 Proof)",
    net="750 mL",
    producer="BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
    heading=WARNING_HEAD,
    head_font="bold",
    body_font="regular",
    warning=True,
    box=True,
    gap=46,
    embed=False,
    country=None,
) -> None:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([28, 28, W - 28, H - 28], outline=GOLD, width=3)

    y = 120
    y = centre(d, y, "EST. 1884", font("serif", 26), GOLD)
    y = centre(d, y + 18, brand, font("serif_bold", 54))
    d.line([(180, y + 14), (W - 180, y + 14)], fill=GOLD, width=2)
    y = centre(d, y + 44, class_type, font("serif", 30))
    y = centre(d, y + 56, abv_text, font("regular", 27))
    y = centre(d, y + 16, net, font("regular", 27))
    if country:
        y = centre(d, y + 16, country, font("regular", 24))

    y = wrap(d, 60, y + 70, producer, font("regular", 19), W - 120)

    if warning and embed:
        # "Separate and apart" fails when the warning is merely another paragraph
        # in a block of body copy, set in the same face at the same size.
        body = font("regular", 20)
        y = wrap(d, 60, y + 8, MARKETING_BEFORE, body, W - 120)
        y = wrap(d, 60, y + 2, f"{heading}{WARNING_BODY}", body, W - 120)
        wrap(d, 60, y + 2, MARKETING_AFTER, body, W - 120)
    elif warning:
        draw_warning(d, y + gap, heading=heading, head_font=head_font, body_font=body_font, box=box)

    img.save(OUT / f"{name}.png")


CASES = {
    "compliant_bourbon": (
        {},
        {"note": "Fully compliant distilled spirits label. Baseline.", "expect_overall": "PASS"},
    ),
    "warning_missing": (
        {"warning": False},
        {"note": "No government warning at all.", "expect_overall": "FAIL", "expect_fail": ["VAL-01"]},
    ),
    "warning_title_case": (
        {"heading": "Government Warning:"},
        {
            "note": "Heading in title case, not capitals. Jenny rejected one of these.",
            "expect_overall": "FAIL",
            "expect_fail": ["VAL-02"],
        },
    ),
    "warning_body_bold": (
        {"body_font": "bold"},
        {
            "note": "Entire warning bolded. §16.22(a)(2) forbids bolding the remainder.",
            "expect_overall": "FAIL",
            "expect_fail": ["VAL-04"],
        },
    ),
    "warning_heading_not_bold": (
        {"head_font": "regular"},
        {"note": "Heading in capitals but not bold.", "expect_overall": "FAIL", "expect_fail": ["VAL-03"]},
    ),
    "abv_proof_only": (
        {"abv_text": "90 Proof"},
        {
            "note": "Proof stated without percent by volume. §5.65 requires ABV.",
            "expect_overall": "FAIL",
            "expect_fail": ["VAL-11"],
        },
    ),
    "producer_no_function_phrase": (
        {"producer": "OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY"},
        {
            "note": "Producer name without 'bottled by' etc. §5.66(b).",
            "expect_overall": "FAIL",
            "expect_fail": ["VAL-12"],
        },
    ),
    "small_bottle_50ml": (
        {"net": "50 mL"},
        {"note": "Miniature. Selects the 1 mm type-size threshold under §16.22(b). No decidable "
                 "defect, so PASS; the type-size caveat is advisory and reported separately.",
         "expect_overall": "PASS"},
    ),
    "imported_no_country": (
        {
            "brand": "GLEN CASTLE",
            "class_type": "Blended Scotch Whisky",
            "producer": "IMPORTED BY ATLANTIC SPIRITS CO., NEWARK, NEW JERSEY",
        },
        {
            "note": "Imported product with no country of origin. §5.69.",
            "expect_overall": "FAIL",
            "expect_fail": ["VAL-13"],
        },
    ),
    "warning_not_separated": (
        {"embed": True},
        {"note": "Warning set as one more paragraph of body copy, same face and size as the "
                 "marketing text around it; §16.21 requires it be separate and apart.",
         "expect_overall": "FAIL", "expect_fail": ["VAL-05"]},
    ),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (kwargs, meta) in CASES.items():
        build(name, **kwargs)
        manifest[f"{name}.png"] = meta
    (OUT / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(CASES)} labels + expected.json to {OUT}")

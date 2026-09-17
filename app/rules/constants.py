"""Regulatory constants, each carrying its citation.

Retrieved from the Government Publishing Office, 27 CFR, 2024 edition. Nothing in
this file may be inlined at a call site: a threshold without its citation is a
number nobody can check.
"""

from typing import Final

# --- 27 CFR 16.21 — mandatory label information ------------------------------
# The statement must appear "separate and apart from all other information".
WARNING_HEADING: Final = "GOVERNMENT WARNING:"

WARNING_STATEMENT: Final = (
    "GOVERNMENT WARNING: "
    "(1) According to the Surgeon General, women should not drink alcoholic beverages "
    "during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

CITE_WARNING_TEXT: Final = "27 CFR 16.21"
CITE_WARNING_TYPOGRAPHY: Final = "27 CFR 16.22(a)(2)"
CITE_WARNING_LEGIBILITY: Final = "27 CFR 16.22(a)(1)"
CITE_WARNING_COMPRESSION: Final = "27 CFR 16.22(a)(3)"
CITE_WARNING_CHARS_PER_INCH: Final = "27 CFR 16.22(a)(4)"
CITE_WARNING_TYPE_SIZE: Final = "27 CFR 16.22(b)"
CITE_FIELD_OF_VISION: Final = "27 CFR 5.63(a)"
CITE_ALCOHOL_CONTENT: Final = "27 CFR 5.65"
CITE_ALCOHOL_TOLERANCE: Final = "27 CFR 5.65(c)"
CITE_PRODUCER_NAME: Final = "27 CFR 5.66(b)"
CITE_COUNTRY_OF_ORIGIN: Final = "27 CFR 5.69"

# --- 27 CFR 16.22(b) — minimum type size by container volume -----------------
# Ordered ascending; the first bracket whose upper bound is not exceeded applies.
# (upper bound in millilitres inclusive, minimum type size in millimetres)
TYPE_SIZE_BRACKETS_ML: Final = (
    (237.0, 1.0),      # containers of 237 mL (8 fl oz) or less
    (3000.0, 2.0),     # more than 237 mL up to 3 L (101 fl oz)
    (float("inf"), 3.0),  # more than 3 L
)

# --- 27 CFR 16.22(a)(4) — maximum characters per inch by type size -----------
MAX_CHARS_PER_INCH: Final = {1.0: 40, 2.0: 25, 3.0: 12}

# --- 27 CFR 5.65(c) — tolerance between stated and actual alcohol content ----
# Governs label-versus-application comparison (MCH-03). It is not permission to
# round a stated value, nor to accept a missing one.
ABV_TOLERANCE_POINTS: Final = 0.3

# --- 27 CFR 5.66(b) — the producer name must be preceded by a function phrase -
# "identified by a phrase describing the function performed by that person".
PRODUCER_FUNCTION_PHRASES: Final = (
    "bottled by",
    "canned by",
    "packed by",
    "filled by",
    "blended by",
    "made by",
    "prepared by",
    "produced by",
    "manufactured by",
    "distilled by",
    "imported by",
    "brewed by",
    "vinted by",
    "cellared by",
)

# Phrases that indicate an imported product, triggering the country-of-origin rule.
IMPORTER_PHRASES: Final = ("imported by",)

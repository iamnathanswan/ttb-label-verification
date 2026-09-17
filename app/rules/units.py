"""Volume parsing.

Net contents is not merely a field to display: 27 CFR 16.22(b) selects the minimum
warning type size from the container volume, so the printed string has to become a
number before VAL-08 can decide anything.
"""

import re

# Multipliers to millilitres. US fluid ounce, not imperial.
_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "millilitre": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "centilitre": 10.0,
    "dl": 100.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "fl oz": 29.5735,
    "fl. oz.": 29.5735,
    "floz": 29.5735,
    "fluid ounce": 29.5735,
    "oz": 29.5735,
    "pint": 473.176,
    "quart": 946.353,
    "gallon": 3785.41,
}

# Longest unit names first so "fluid ounce" is not matched as "oz".
_UNIT_ALTERNATION = "|".join(sorted((re.escape(u) for u in _TO_ML), key=len, reverse=True))
_PATTERN = re.compile(
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_ALTERNATION})\b",
    re.IGNORECASE,
)


def parse_volume_ml(text: str | None) -> float | None:
    """Return the volume in millilitres, or None if it cannot be determined.

    None is a meaningful answer: a label whose net contents could not be read
    cannot have its warning type size evaluated, and must go to review rather
    than be assigned a threshold by guesswork.
    """
    if not text:
        return None
    match = _PATTERN.search(text.strip())
    if not match:
        return None
    raw = match.group("value").replace(",", ".")
    unit = match.group("unit").lower().rstrip(".")
    factor = _TO_ML.get(unit) or _TO_ML.get(unit.replace(".", ""))
    if factor is None:
        return None
    try:
        return float(raw) * factor
    except ValueError:
        return None


def minimum_type_size_mm(volume_ml: float) -> float:
    """Minimum warning type size for a container of this volume (27 CFR 16.22(b))."""
    from app.rules.constants import TYPE_SIZE_BRACKETS_ML

    for upper, size_mm in TYPE_SIZE_BRACKETS_ML:
        if volume_ml <= upper:
            return size_mm
    return TYPE_SIZE_BRACKETS_ML[-1][1]

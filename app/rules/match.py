"""Label-versus-application matching — MCH-01 through MCH-06.

Normalisation here is the opposite of `warning.py`, and the contrast is the point.
27 CFR 16.21 prescribes the warning word for word, so that module compares
exactly. Nothing prescribes how a brand name is capitalised, so this module folds
case, punctuation, whitespace and accents before comparing: "STONE'S THROW"
against "Stone's Throw" is the same brand, and a tool that rejects it is worse
than the eye it replaced.

The two policies must never share a helper.
"""

import re
import unicodedata

from app.models import CheckResult, ExpectedValues, LabelFields, Status
from app.rules import constants as C
from app.rules.units import parse_volume_ml


def normalise(text: str) -> str:
    """Fold everything that is not a substantive difference.

    Accents are stripped, case folded, punctuation dropped, whitespace collapsed.
    Used only for comparison; the original strings are always shown to the agent.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w\s]", " ", without_accents).lower().split())


def _text_match(
    *, id_: str, name: str, expected: str | None, observed: str | None, citation: str | None = None
) -> CheckResult | None:
    """Compare one free-text field. Returns None when there is nothing to compare."""
    if expected is None or not expected.strip():
        return None

    observed = (observed or "").strip()
    if not observed:
        return CheckResult(
            id=id_, name=name, status=Status.FAIL, citation=citation,
            expected=expected, observed=None,
            detail=f"The application states “{expected}” but nothing corresponding was found on the label.",
        )

    if observed == expected.strip():
        return CheckResult(
            id=id_, name=name, status=Status.PASS, citation=citation,
            expected=expected, observed=observed,
            detail="Label and application agree exactly.",
        )

    if normalise(observed) == normalise(expected):
        return CheckResult(
            id=id_, name=name, status=Status.REVIEW, citation=citation,
            expected=expected, observed=observed,
            detail=(
                "Label and application differ only in capitalisation, punctuation or spacing. "
                "Confirm this is the same designation."
            ),
        )

    return CheckResult(
        id=id_, name=name, status=Status.FAIL, citation=citation,
        expected=expected, observed=observed,
        detail=f"The application states “{expected}” but the label reads “{observed}”.",
    )


def check_alcohol_content(expected_pct: float | None, fields: LabelFields) -> CheckResult | None:
    """MCH-03 — 27 CFR 5.65(c) allows ±0.3 percentage points.

    A difference inside the tolerance is a match, not a discrepancy to be argued
    about. Outside it, the shortfall is quantified rather than merely flagged.
    """
    if expected_pct is None:
        return None

    observed = fields.alcohol_content_pct
    if observed is None:
        return CheckResult(
            id="MCH-03", name="Alcohol content matches application", status=Status.FAIL,
            citation=C.CITE_ALCOHOL_TOLERANCE, expected=f"{expected_pct:g}%",
            detail=f"The application states {expected_pct:g}% but no alcohol content was found on the label.",
        )

    difference = abs(observed - expected_pct)
    within = difference <= C.ABV_TOLERANCE_POINTS
    return CheckResult(
        id="MCH-03", name="Alcohol content matches application",
        status=Status.PASS if within else Status.FAIL,
        citation=C.CITE_ALCOHOL_TOLERANCE,
        expected=f"{expected_pct:g}%", observed=f"{observed:g}%",
        detail=(
            f"Label {observed:g}% against application {expected_pct:g}% — a difference of "
            f"{difference:.2g} points, within the permitted ±{C.ABV_TOLERANCE_POINTS} points."
            if within
            else
            f"Label {observed:g}% against application {expected_pct:g}% — a difference of "
            f"{difference:.2g} points, outside the permitted ±{C.ABV_TOLERANCE_POINTS} points."
        ),
    )


def check_net_contents(expected: str | None, fields: LabelFields) -> CheckResult | None:
    """Compare declared volume by value, so "750 mL" and "750ML" agree."""
    if not expected or not expected.strip():
        return None

    observed_raw = (fields.net_contents_raw or "").strip()
    expected_ml, observed_ml = parse_volume_ml(expected), parse_volume_ml(observed_raw)

    if expected_ml is not None and observed_ml is not None:
        if abs(expected_ml - observed_ml) < 0.5:
            return CheckResult(
                id="MCH-01", name="Net contents matches application", status=Status.PASS,
                expected=expected, observed=observed_raw,
                detail=f"Both state {observed_ml:g} mL.",
            )
        return CheckResult(
            id="MCH-01", name="Net contents matches application", status=Status.FAIL,
            expected=expected, observed=observed_raw,
            detail=f"The application states {expected_ml:g} mL but the label states {observed_ml:g} mL.",
        )

    return _text_match(id_="MCH-01", name="Net contents matches application",
                       expected=expected, observed=observed_raw)


def check_all(fields: LabelFields, expected: ExpectedValues | None) -> list[CheckResult]:
    """Every applicable comparison. Empty when no application values were supplied.

    MCH-06 — expected values are optional. Without them the compliance checks
    still run; only the matching layer is skipped.
    """
    if expected is None:
        return []

    candidates = [
        _text_match(id_="MCH-01", name="Brand name matches application",
                    expected=expected.brand_name, observed=fields.brand_name),
        _text_match(id_="MCH-01", name="Class/type matches application",
                    expected=expected.class_type, observed=fields.class_type),
        check_alcohol_content(expected.alcohol_content_pct, fields),
        check_net_contents(expected.net_contents, fields),
        _text_match(id_="MCH-01", name="Producer matches application",
                    expected=expected.producer_name, observed=fields.producer_name),
        _text_match(id_="MCH-01", name="Country of origin matches application",
                    expected=expected.country_of_origin, observed=fields.country_of_origin,
                    citation=C.CITE_COUNTRY_OF_ORIGIN),
    ]
    return [c for c in candidates if c is not None]

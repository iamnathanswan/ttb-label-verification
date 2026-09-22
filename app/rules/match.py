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

from app.models import ApplicationFields, CheckResult, LabelFields, Status
from app.rules import constants as C


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
            id=id_,
            name=name,
            status=Status.FAIL,
            citation=citation,
            expected=expected,
            observed=None,
            detail=f"The application states “{expected}” but nothing corresponding was found on the label.",
        )

    if observed == expected.strip():
        return CheckResult(
            id=id_,
            name=name,
            status=Status.PASS,
            citation=citation,
            expected=expected,
            observed=observed,
            detail="Label and application agree exactly.",
        )

    if normalise(observed) == normalise(expected):
        return CheckResult(
            id=id_,
            name=name,
            status=Status.REVIEW,
            citation=citation,
            expected=expected,
            observed=observed,
            detail=(
                "Label and application differ only in capitalisation, punctuation or spacing. "
                "Confirm this is the same designation."
            ),
        )

    return CheckResult(
        id=id_,
        name=name,
        status=Status.FAIL,
        citation=citation,
        expected=expected,
        observed=observed,
        detail=f"The application states “{expected}” but the label reads “{observed}”.",
    )


def check_producer(application: ApplicationFields, fields: LabelFields) -> CheckResult | None:
    """Compare field 8 against the producer statement on the label.

    Field 8 is the applicant's *name and address* as one string; the label carries
    them as separate statements under §5.66. So the two are never character
    identical and a plain string comparison fails every time, including on a
    perfectly matching pair.

    The form also instructs applicants to include an approved DBA or trade name
    where it is used on the label, so the two can legitimately differ in wording.
    Containment is therefore treated as agreement, and anything less certain goes
    to a person rather than being called a discrepancy.
    """
    declared = (application.applicant_name or "").strip()
    if not declared:
        return None

    on_label = " ".join(
        part for part in ((fields.producer_name or ""), (fields.producer_address or "")) if part.strip()
    ).strip()

    if not on_label:
        return CheckResult(
            id="MCH-01",
            name="Producer matches application",
            status=Status.FAIL,
            citation=C.CITE_PRODUCER_NAME,
            expected=declared,
            observed=None,
            detail=f"The application names “{declared}” but no producer was found on the label.",
        )

    declared_norm, label_norm = normalise(declared), normalise(on_label)

    if declared_norm == label_norm:
        return CheckResult(
            id="MCH-01",
            name="Producer matches application",
            status=Status.PASS,
            citation=C.CITE_PRODUCER_NAME,
            expected=declared,
            observed=on_label,
            detail="The producer on the label matches the applicant on the application.",
        )

    if label_norm in declared_norm or declared_norm in label_norm:
        return CheckResult(
            id="MCH-01",
            name="Producer matches application",
            status=Status.PASS,
            citation=C.CITE_PRODUCER_NAME,
            expected=declared,
            observed=on_label,
            detail=(
                "The producer on the label corresponds to the applicant on the application; "
                "the application states the fuller name and address."
            ),
        )

    # Share the leading words? Likely the same entity written two ways.
    declared_words, label_words = declared_norm.split(), label_norm.split()
    if declared_words[:2] and declared_words[:2] == label_words[:2]:
        return CheckResult(
            id="MCH-01",
            name="Producer matches application",
            status=Status.REVIEW,
            citation=C.CITE_PRODUCER_NAME,
            expected=declared,
            observed=on_label,
            detail=(
                "The producer and the applicant begin with the same name but differ afterwards. "
                "Confirm they are the same entity — a trade name may be in use on the label."
            ),
        )

    return CheckResult(
        id="MCH-01",
        name="Producer matches application",
        status=Status.FAIL,
        citation=C.CITE_PRODUCER_NAME,
        expected=declared,
        observed=on_label,
        detail=f"The application names “{declared}” but the label states “{on_label}”.",
    )


def check_all(fields: LabelFields, application: ApplicationFields | None) -> list[CheckResult]:
    """Compare the label against the application. Empty when none was paired.

    Both sides are extracted, so this compares what was read from the label to
    what was read from the form — no one retypes anything, which is the point.

    Only what the form actually declares is compared. Net contents and alcohol
    content are not fields on TTB F 5100.31 — field 15 asks for container wording
    only where it does *not* appear on the labels, which is a fallback rather than
    a value to compare. Both are verified against the label's own requirements
    instead (VAL-11, VAL-14, VAL-08). Source and type are declarations that decide which rules apply, so
    they are consumed by VAL-13 and by the commodity gating in `engine.py` rather
    than matched field to field.
    """
    if application is None:
        return []

    candidates = [
        _text_match(
            id_="MCH-01",
            name="Brand name matches application",
            expected=application.brand_name,
            observed=fields.brand_name,
        ),
        _text_match(
            id_="MCH-01",
            name="Fanciful name matches application",
            expected=application.fanciful_name,
            observed=fields.brand_name,
        ),
        check_producer(application, fields),
    ]
    return [c for c in candidates if c is not None]

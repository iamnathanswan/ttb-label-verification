"""Mandatory label field checks — VAL-10 through VAL-14.

These are Part 5 (distilled spirits) rules. Parts 4 and 7 govern wine and malt
beverages and differ; `engine.py` gates them by beverage type so a wine label is
marked unverified rather than failed against rules that do not apply to it
(docs/requirements.md §J-4).
"""

from app.models import CheckResult, LabelFields, Status
from app.rules import constants as C
from app.rules.observation import from_observation

# Fields mandatory on a distilled spirits label, with the citation for each.
MANDATORY = (
    ("brand_name", "Brand name", "27 CFR 5.64"),
    ("class_type", "Class/type designation", "27 CFR 5.63(a)(2)"),
    ("net_contents_raw", "Net contents", "27 CFR 5.70"),
    ("producer_name", "Producer name and address", C.CITE_PRODUCER_NAME),
)


def check_mandatory_present(fields: LabelFields) -> list[CheckResult]:
    """VAL-14 — each missing field is reported on its own.

    Collapsing four absences into one failure tells an agent to go looking; naming
    them tells them what to write in the rejection.
    """
    results = []
    for attr, label, citation in MANDATORY:
        value = (getattr(fields, attr) or "").strip()
        results.append(
            CheckResult(
                id="VAL-14",
                name=f"{label} present",
                citation=citation,
                status=Status.PASS if value else Status.FAIL,
                observed=value or None,
                detail=(
                    f"{label} found: “{value}”." if value else f"{label} is required but was not found on this label."
                ),
            )
        )
    return results


def check_alcohol_content(fields: LabelFields) -> CheckResult:
    """VAL-11 — 27 CFR 5.65 requires a percentage by volume.

    Degrees proof may appear in addition but never instead, so a label showing
    "90 Proof" alone fails even though the strength is unambiguous to a reader.
    """
    if fields.alcohol_content_pct is not None:
        stated = f"{fields.alcohol_content_pct:g}% alc./vol."
        if fields.alcohol_content_proof is not None:
            stated += f" ({fields.alcohol_content_proof:g} proof)"
        return CheckResult(
            id="VAL-11",
            name="Alcohol content stated as percent by volume",
            status=Status.PASS,
            citation=C.CITE_ALCOHOL_CONTENT,
            observed=stated,
            detail=f"Alcohol content is stated as a percentage by volume: {stated}.",
        )

    if fields.alcohol_content_proof is not None:
        return CheckResult(
            id="VAL-11",
            name="Alcohol content stated as percent by volume",
            status=Status.FAIL,
            citation=C.CITE_ALCOHOL_CONTENT,
            observed=f"{fields.alcohol_content_proof:g} proof",
            expected="percentage of alcohol by volume",
            detail=(
                f"Only degrees proof ({fields.alcohol_content_proof:g}) is shown. Alcohol content must be "
                "stated as a percentage by volume; proof may be added but cannot replace it."
            ),
        )

    return CheckResult(
        id="VAL-11",
        name="Alcohol content stated as percent by volume",
        status=Status.FAIL,
        citation=C.CITE_ALCOHOL_CONTENT,
        expected="percentage of alcohol by volume",
        detail="No alcohol content statement was found on this label.",
    )


def check_producer_function_phrase(fields: LabelFields) -> CheckResult:
    """VAL-12 — 27 CFR 5.66(b): the name must be preceded by a function phrase."""
    phrase = (fields.producer_function_phrase or "").strip().lower().rstrip(":")

    if not (fields.producer_name or "").strip():
        return CheckResult(
            id="VAL-12",
            name="Producer function phrase",
            status=Status.REVIEW,
            citation=C.CITE_PRODUCER_NAME,
            detail="No producer name was found, so the accompanying function phrase cannot be assessed.",
        )

    if phrase and any(phrase.startswith(known) or known in phrase for known in C.PRODUCER_FUNCTION_PHRASES):
        return CheckResult(
            id="VAL-12",
            name="Producer function phrase",
            status=Status.PASS,
            citation=C.CITE_PRODUCER_NAME,
            observed=fields.producer_function_phrase,
            detail=f"The producer name is preceded by “{fields.producer_function_phrase}”.",
        )

    if phrase:
        return CheckResult(
            id="VAL-12",
            name="Producer function phrase",
            status=Status.REVIEW,
            citation=C.CITE_PRODUCER_NAME,
            observed=fields.producer_function_phrase,
            expected="a phrase describing the function performed, e.g. “bottled by”",
            detail=(
                f"“{fields.producer_function_phrase}” was found before the producer name but is not a "
                "recognised function phrase. Confirm it describes the function performed."
            ),
        )

    return CheckResult(
        id="VAL-12",
        name="Producer function phrase",
        status=Status.FAIL,
        citation=C.CITE_PRODUCER_NAME,
        observed=fields.producer_name,
        expected="a phrase describing the function performed, e.g. “bottled by”",
        detail=(
            "The producer name appears without a phrase describing the function performed. "
            "The name must be preceded by wording such as “bottled by” or “distilled by”."
        ),
    )


def check_country_of_origin(fields: LabelFields) -> CheckResult:
    """VAL-13 — 27 CFR 5.69: required for imported products.

    Import status is inferred from the function phrase, which is the only signal a
    label reliably carries. When nothing indicates importation the rule does not
    apply, and saying so is more useful than a silent pass.
    """
    phrase = (fields.producer_function_phrase or "").lower()
    looks_imported = any(marker in phrase for marker in C.IMPORTER_PHRASES)
    country = (fields.country_of_origin or "").strip()

    if country:
        return CheckResult(
            id="VAL-13",
            name="Country of origin",
            status=Status.PASS,
            citation=C.CITE_COUNTRY_OF_ORIGIN,
            observed=country,
            detail=f"Country of origin is stated: {country}.",
        )

    if looks_imported:
        return CheckResult(
            id="VAL-13",
            name="Country of origin",
            status=Status.FAIL,
            citation=C.CITE_COUNTRY_OF_ORIGIN,
            expected="country of origin",
            detail=(
                "The label indicates an imported product but states no country of origin, "
                "which is required for imports."
            ),
        )

    return CheckResult(
        id="VAL-13",
        name="Country of origin",
        status=Status.PASS,
        citation=C.CITE_COUNTRY_OF_ORIGIN,
        detail="Not applicable: nothing on the label indicates an imported product.",
    )


def check_field_of_vision(fields: LabelFields) -> CheckResult:
    """VAL-10 — 27 CFR 5.63(a): brand, class/type and alcohol content together."""
    return from_observation(
        fields.same_field_of_vision,
        id_="VAL-10",
        name="Same field of vision",
        requirement=(
            "brand name, class/type designation and alcohol content all appear within the same field of vision"
        ),
        citation=C.CITE_FIELD_OF_VISION,
    )


def check_all(fields: LabelFields) -> list[CheckResult]:
    """Every mandatory-field check, VAL-10 through VAL-14."""
    return [
        check_field_of_vision(fields),
        check_alcohol_content(fields),
        check_producer_function_phrase(fields),
        check_country_of_origin(fields),
        *check_mandatory_present(fields),
    ]

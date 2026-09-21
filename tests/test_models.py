"""The extraction contract — EXT-01 through EXT-08.

`LabelFields` is the boundary between the model and the rules (D2). What the
schema promises to carry is therefore a requirement in its own right: a field
quietly dropped here would silently disable whichever rule depends on it, and
every rule test would still pass.

End-to-end extraction of these fields from real images is verified separately by
`scripts/verify_corpus.py`; this pins the shape.
"""

import pytest

from app.models import ApplicationFields, CheckResult, LabelFields, Status, VerificationResult

# Requirement -> the field that satisfies it.
MANDATORY_FIELDS = {
    "EXT-01": "brand_name",
    "EXT-02": "class_type",
    "EXT-03": "alcohol_content_pct",
    "EXT-04": "net_contents_raw",
    "EXT-05": "producer_name",
    "EXT-06": "country_of_origin",
    "EXT-07": "warning_text",
}


@pytest.mark.parametrize("requirement,field", sorted(MANDATORY_FIELDS.items()))
def test_extraction_schema_carries_every_mandatory_field(requirement, field):
    assert field in LabelFields.model_fields, f"{requirement} has no field on the contract"


def test_ext_08_low_confidence_fields_are_reportable():
    fields = LabelFields(low_confidence_fields=["brand_name"])
    assert fields.low_confidence_fields == ["brand_name"]


def test_absent_text_is_falsy_so_rules_need_not_special_case_it():
    """Absent values are empty strings, not null; rules test falsiness (see models)."""
    blank = LabelFields()
    for field in ("brand_name", "class_type", "net_contents_raw", "producer_name", "warning_text"):
        assert not getattr(blank, field)


def test_alcohol_content_stays_nullable_because_zero_is_a_real_value():
    assert LabelFields().alcohol_content_pct is None
    assert LabelFields(alcohol_content_pct=0.0).alcohol_content_pct == 0.0


def test_observations_default_to_unclear_not_to_a_verdict():
    """An unset visual reading must not be mistaken for a compliant one."""
    blank = LabelFields()
    for field in ("warning_heading_is_caps", "warning_heading_is_bold", "warning_body_is_bold"):
        assert getattr(blank, field) == "unclear"


def test_result_separates_failures_reviews_and_advisories():
    result = VerificationResult(
        overall=Status.FAIL,
        fields=LabelFields(),
        elapsed_ms=0,
        checks=[
            CheckResult(id="VAL-01", name="a", status=Status.FAIL, detail="x"),
            CheckResult(id="VAL-02", name="b", status=Status.REVIEW, detail="x"),
            CheckResult(id="VAL-08", name="c", status=Status.REVIEW, detail="x", advisory=True),
            CheckResult(id="VAL-03", name="d", status=Status.PASS, detail="x"),
        ],
    )
    assert [c.id for c in result.failures] == ["VAL-01"]
    assert [c.id for c in result.reviews] == ["VAL-02"], "advisories must not appear as reviews"
    assert [c.id for c in result.advisories] == ["VAL-08"]


def test_application_fields_are_all_optional():
    """MCH-06 — the tool must work with no application at all."""
    assert ApplicationFields().is_empty


# --- two questions, kept apart ------------------------------------------------


def test_checks_are_categorised_by_the_question_they_answer():
    """Compliance and matching are acted on differently.

    A label can match its application exactly and still be unlawful, and can be
    perfectly lawful while disagreeing with the form — which is as often fixed by
    correcting the application as the label.
    """
    result = VerificationResult(
        overall=Status.FAIL,
        fields=LabelFields(),
        elapsed_ms=0,
        checks=[
            CheckResult(id="VAL-01", name="warning", status=Status.FAIL, detail="x"),
            CheckResult(id="MCH-01", name="brand", status=Status.REVIEW, detail="x"),
            CheckResult(id="VAL-08", name="type size", status=Status.REVIEW, detail="x", advisory=True),
            CheckResult(id="EXT-09", name="legible", status=Status.REVIEW, detail="x"),
        ],
    )
    assert [c.id for c in result.matching_checks] == ["MCH-01"]
    assert [c.id for c in result.compliance_checks] == ["VAL-01", "EXT-09"]
    assert [c.id for c in result.advisories] == ["VAL-08"]


def test_category_is_serialised_for_the_interface():
    check = CheckResult(id="MCH-01", name="brand", status=Status.PASS, detail="x")
    assert check.model_dump()["category"] == "matching"


def test_a_label_with_no_application_has_no_matching_checks():
    result = VerificationResult(
        overall=Status.PASS,
        fields=LabelFields(),
        elapsed_ms=0,
        checks=[CheckResult(id="VAL-01", name="warning", status=Status.PASS, detail="x")],
    )
    assert result.matching_checks == []
    assert result.compliance_checks

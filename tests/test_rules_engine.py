"""Engine composition tests — gating, overall status, legibility. No network."""

from app.models import ApplicationFields, LabelFields, Status
from app.rules import constants as C
from app.rules.engine import evaluate, overall_status, verify


def compliant(**overrides) -> LabelFields:
    """A fully compliant distilled spirits label, before overrides."""
    base = dict(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content_pct=45.0,
        alcohol_content_proof=90.0,
        net_contents_raw="750 mL",
        producer_name="OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
        producer_function_phrase="BOTTLED BY",
        warning_text=C.WARNING_STATEMENT,
        warning_heading_is_caps="yes",
        warning_heading_is_bold="yes",
        warning_body_is_bold="no",
        warning_visually_separated="yes",
        warning_on_contrasting_background="yes",
        same_field_of_vision="yes",
        beverage_type="distilled_spirits",
    )
    return LabelFields(**{**base, **overrides})


# --- overall status -----------------------------------------------------------


def test_compliant_label_passes():
    """A label with no decidable defect must reach PASS.

    Advisory measurement rules fire on every label alike, so including them in the
    verdict would make PASS unreachable and the verdict uninformative.
    """
    result = verify(compliant())
    assert result.overall is Status.PASS
    assert not result.failures
    assert result.advisories, "advisory caveats should still be reported"


def test_a_single_failure_fails_the_label():
    result = verify(compliant(warning_body_is_bold="yes"))
    assert result.overall is Status.FAIL
    assert any(c.id == "VAL-04" for c in result.failures)


def test_advisory_checks_do_not_drive_the_verdict():
    checks = evaluate(compliant())
    assert overall_status(checks) is Status.PASS
    assert [c for c in checks if c.advisory and c.status is Status.REVIEW]


def test_a_decidable_review_still_shows_as_review():
    assert verify(compliant(warning_heading_is_bold="unclear")).overall is Status.REVIEW


# --- legibility short-circuit (UX-08) ----------------------------------------


def test_illegible_image_asks_for_a_better_photograph():
    result = verify(compliant(image_legible=False, illegible_reason="heavy glare"))
    assert len(result.checks) == 1
    assert result.overall is Status.REVIEW
    assert "clearer photograph" in result.checks[0].detail
    assert "glare" in result.checks[0].detail


# --- beverage type gating (§J-4) ---------------------------------------------


def test_wine_label_is_not_failed_against_spirits_rules():
    """Part 5 rules do not govern wine; declining to judge beats judging wrongly."""
    wine = compliant(beverage_type="wine", alcohol_content_pct=None, producer_function_phrase="")
    result = verify(wine)
    softened = [c for c in result.checks if c.id in {"VAL-11", "VAL-12"}]
    assert softened and all(c.status is Status.REVIEW for c in softened)
    assert all("Part 5" in c.detail for c in softened)


def test_warning_rules_still_apply_to_wine():
    """Part 16 is universal — a wine label with no warning still fails."""
    wine = compliant(beverage_type="wine", warning_text="")
    result = verify(wine)
    assert result.overall is Status.FAIL
    assert any(c.id == "VAL-01" for c in result.failures)


def test_spirits_rules_are_not_softened_for_spirits():
    result = verify(compliant(alcohol_content_pct=None, alcohol_content_proof=90.0))
    assert any(c.id == "VAL-11" and c.status is Status.FAIL for c in result.checks)


# --- MCH-06 — matching is optional -------------------------------------------


def test_verification_works_without_application_values():
    result = verify(compliant())
    assert not [c for c in result.checks if c.id.startswith("MCH")]
    assert result.overall is not Status.FAIL


def test_application_values_add_comparisons():
    result = verify(compliant(), ApplicationFields(brand_name="OLD TOM DISTILLERY"))
    assert [c for c in result.checks if c.id.startswith("MCH")]


def test_declared_product_type_decides_which_rules_apply():
    """Field 5 is authoritative; the label should not have to be guessed from."""
    label = compliant(beverage_type="unknown", alcohol_content_pct=None)
    result = verify(label, ApplicationFields(type_of_product="wine"))
    val_11 = next(c for c in result.checks if c.id == "VAL-11")
    assert val_11.status is Status.REVIEW
    assert "Part 5" in val_11.detail


def test_label_disagreeing_with_the_declared_type_is_surfaced():
    result = verify(compliant(), ApplicationFields(type_of_product="wine"))
    mismatch = [c for c in result.checks if c.name == "Product type matches application"]
    assert mismatch and mismatch[0].status is Status.REVIEW


# --- result shape -------------------------------------------------------------


def test_every_check_carries_an_id_and_actionable_detail():
    for check in verify(compliant(warning_text="")).checks:
        assert check.id and check.detail
        assert len(check.detail) > 20


def test_result_records_timing_and_filename():
    result = verify(compliant(), elapsed_ms=4200, filename="bourbon.png")
    assert result.elapsed_ms == 4200 and result.filename == "bourbon.png"

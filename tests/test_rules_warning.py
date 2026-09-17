"""Warning rule tests — VAL-01..09. No network, no API key."""

import pytest

from app.models import LabelFields, Status
from app.rules import constants as C
from app.rules.warning import check_all, check_warning_text, describe_first_difference


def compliant(**overrides) -> LabelFields:
    """A label that satisfies every warning rule, before overrides."""
    base = dict(
        warning_text=C.WARNING_STATEMENT,
        warning_heading_is_caps="yes",
        warning_heading_is_bold="yes",
        warning_body_is_bold="no",
        warning_visually_separated="yes",
        warning_on_contrasting_background="yes",
        net_contents_raw="750 mL",
    )
    return LabelFields(**{**base, **overrides})


def status_of(fields: LabelFields, check_id: str) -> Status:
    return next(c.status for c in check_all(fields) if c.id == check_id)


# --- VAL-01 — exact text ------------------------------------------------------

def test_val_01_exact_statement_passes():
    assert check_warning_text(compliant()).status is Status.PASS


def test_val_01_tolerates_only_whitespace_differences():
    spaced = C.WARNING_STATEMENT.replace(" ", "  ").replace("(2)", "\n(2)")
    assert check_warning_text(compliant(warning_text=spaced)).status is Status.PASS


def test_val_01_missing_warning_fails():
    result = check_warning_text(compliant(warning_text=""))
    assert result.status is Status.FAIL
    assert "mandatory" in result.detail


def test_val_01_single_word_change_fails_and_is_explained():
    altered = C.WARNING_STATEMENT.replace("birth defects", "birth defect")
    result = check_warning_text(compliant(warning_text=altered))
    assert result.status is Status.FAIL
    assert "defect" in result.detail


def test_val_01_is_case_sensitive():
    """Case folding here would hide a genuine rejection; see module docstring."""
    lowered = C.WARNING_STATEMENT.replace("GOVERNMENT WARNING:", "Government Warning:")
    assert check_warning_text(compliant(warning_text=lowered)).status is Status.FAIL


# --- VAL-02, VAL-03, VAL-04 — typography -------------------------------------

def test_val_02_title_case_heading_fails():
    assert status_of(compliant(warning_heading_is_caps="no"), "VAL-02") is Status.FAIL


def test_val_03_heading_not_bold_fails():
    assert status_of(compliant(warning_heading_is_bold="no"), "VAL-03") is Status.FAIL


def test_val_04_warning_body_bold_fails():
    """27 CFR 16.22(a)(2) forbids bolding the remainder. Mentioned in no interview."""
    assert status_of(compliant(warning_body_is_bold="yes"), "VAL-04") is Status.FAIL


def test_val_04_body_not_bold_passes():
    assert status_of(compliant(warning_body_is_bold="no"), "VAL-04") is Status.PASS


@pytest.mark.parametrize("check_id,field", [
    ("VAL-02", "warning_heading_is_caps"),
    ("VAL-03", "warning_heading_is_bold"),
    ("VAL-04", "warning_body_is_bold"),
])
def test_unclear_observations_route_to_review(check_id, field):
    """"unclear" must never be silently read as compliant or as a failure."""
    assert status_of(compliant(**{field: "unclear"}), check_id) is Status.REVIEW


# --- VAL-05 — separation ------------------------------------------------------

def test_val_05_not_separated_fails():
    assert status_of(compliant(warning_visually_separated="no"), "VAL-05") is Status.FAIL


# --- VAL-06..09 — advisory only ----------------------------------------------

@pytest.mark.parametrize("check_id", ["VAL-06", "VAL-07", "VAL-08", "VAL-09"])
def test_measurement_rules_never_hard_fail(check_id):
    """A photograph has no millimetre scale (D6). These may not produce FAIL."""
    worst = compliant(warning_on_contrasting_background="no", net_contents_raw="")
    check = next(c for c in check_all(worst) if c.id == check_id)
    assert check.status is not Status.FAIL
    assert check.advisory is True


def test_val_08_selects_threshold_from_container_volume():
    small = next(c for c in check_all(compliant(net_contents_raw="50 mL")) if c.id == "VAL-08")
    large = next(c for c in check_all(compliant(net_contents_raw="750 mL")) if c.id == "VAL-08")
    assert "1 mm" in small.detail
    assert "2 mm" in large.detail


def test_val_08_unknown_volume_says_so():
    check = next(c for c in check_all(compliant(net_contents_raw="")) if c.id == "VAL-08")
    assert check.status is Status.REVIEW
    assert "could not be read" in check.detail


# --- diff helper --------------------------------------------------------------

def test_difference_description_quotes_both_sides():
    described = describe_first_difference("the quick brown fox", "the quick red fox")
    assert "brown" in described and "red" in described

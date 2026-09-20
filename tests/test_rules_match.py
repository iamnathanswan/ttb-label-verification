"""Label-versus-application matching tests — MCH-01..06. No network."""

import pytest

from app.models import ApplicationFields, LabelFields, Status
from app.rules.match import check_all, normalise


def labelled(**overrides) -> LabelFields:
    base = dict(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content_pct=45.0,
        net_contents_raw="750 mL",
        producer_name="Old Tom Distillery",
    )
    return LabelFields(**{**base, **overrides})


def named(results, fragment):
    return next(c for c in results if fragment in c.name.lower())


# --- MCH-06 — expected values are optional -----------------------------------


def test_source_and_type_are_not_matched_field_to_field():
    """They decide which rules apply; VAL-13 and the engine consume them."""
    results = check_all(labelled(), ApplicationFields(source_of_product="imported", type_of_product="wine"))
    assert results == []


def test_no_application_values_produces_no_comparisons():
    assert check_all(labelled(), None) == []


def test_partial_application_values_compare_only_what_was_given():
    results = check_all(labelled(), ApplicationFields(brand_name="OLD TOM DISTILLERY"))
    assert len(results) == 1


# --- MCH-02 — normalisation folds insubstantial differences ------------------


def test_mch_02_case_difference_is_review_not_failure():
    """Dave's case: STONE'S THROW against Stone's Throw is the same brand."""
    results = check_all(
        labelled(brand_name="STONE'S THROW"),
        ApplicationFields(brand_name="Stone's Throw"),
    )
    result = named(results, "brand")
    assert result.status is Status.REVIEW
    assert result.expected == "Stone's Throw" and result.observed == "STONE'S THROW"


def test_mch_02_exact_match_passes_outright():
    results = check_all(labelled(), ApplicationFields(brand_name="OLD TOM DISTILLERY"))
    assert named(results, "brand").status is Status.PASS


def test_mch_02_genuinely_different_name_fails():
    results = check_all(labelled(), ApplicationFields(brand_name="YOUNG TOM DISTILLERY"))
    assert named(results, "brand").status is Status.FAIL


def test_mch_02_missing_on_label_fails():
    results = check_all(labelled(brand_name=""), ApplicationFields(brand_name="OLD TOM"))
    assert named(results, "brand").status is Status.FAIL


@pytest.mark.parametrize(
    "a,b",
    [
        ("Café Noir", "CAFE NOIR"),
        ("Smith & Sons", "smith and sons".replace(" and ", " & ")),
        ("  spaced   out  ", "Spaced Out"),
    ],
)
def test_normalise_folds_accents_punctuation_and_spacing(a, b):
    assert normalise(a) == normalise(b)


def test_normalise_does_not_fold_different_words():
    assert normalise("Old Tom") != normalise("Young Tom")


# --- retired comparisons ------------------------------------------------------


def test_alcohol_and_net_contents_are_not_compared_to_the_application():
    """Neither is a field on TTB F 5100.31, so there is nothing to compare against.

    TTB removed both, and field 15 asks for container wording only where it does
    not appear on the labels. They are verified against the label's own
    requirements instead — VAL-11, VAL-14 and VAL-08. Comparing them to a form
    that does not collect them would be inventing a discrepancy.
    """
    assert "alcohol_content_pct" not in ApplicationFields.model_fields
    assert "net_contents" not in ApplicationFields.model_fields


# --- MCH-05 — every finding shows both sides ---------------------------------


def test_every_non_passing_result_shows_expected_and_observed():
    results = check_all(
        labelled(brand_name="STONE'S THROW", alcohol_content_pct=40.0),
        ApplicationFields(brand_name="Stone's Throw", alcohol_content_pct=45.0),
    )
    for check in results:
        if check.status is not Status.PASS:
            assert check.expected and check.observed, f"{check.name} hides one side"


# --- producer: field 8 is name AND address ------------------------------------


def test_producer_matches_when_the_application_carries_the_address():
    """Field 8 combines name and address; the label separates them.

    A plain string comparison failed every pair, including perfectly matching
    ones, because the two are never character identical.
    """
    from app.rules.match import check_producer

    result = check_producer(
        ApplicationFields(applicant_name="OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY 40004"),
        LabelFields(producer_name="OLD TOM DISTILLERY"),
    )
    assert result.status is Status.PASS


def test_producer_trade_name_variant_goes_to_review():
    """The form tells applicants to include a DBA where the label uses one."""
    from app.rules.match import check_producer

    result = check_producer(
        ApplicationFields(applicant_name="OLD TOM DISTILLERY LLC"),
        LabelFields(producer_name="OLD TOM DISTILLERY COMPANY"),
    )
    assert result.status is Status.REVIEW


def test_a_genuinely_different_producer_fails():
    from app.rules.match import check_producer

    result = check_producer(
        ApplicationFields(applicant_name="ATLANTIC SPIRITS CO., NEWARK, NEW JERSEY"),
        LabelFields(producer_name="OLD TOM DISTILLERY"),
    )
    assert result.status is Status.FAIL

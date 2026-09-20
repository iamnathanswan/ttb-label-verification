"""Label-versus-application matching tests — MCH-01..06. No network."""

import pytest

from app.models import ExpectedValues, LabelFields, Status
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
    results = check_all(labelled(), ExpectedValues(source_of_product="imported", type_of_product="wine"))
    assert results == []


def test_no_application_values_produces_no_comparisons():
    assert check_all(labelled(), None) == []


def test_partial_application_values_compare_only_what_was_given():
    results = check_all(labelled(), ExpectedValues(brand_name="OLD TOM DISTILLERY"))
    assert len(results) == 1


# --- MCH-02 — normalisation folds insubstantial differences ------------------


def test_mch_02_case_difference_is_review_not_failure():
    """Dave's case: STONE'S THROW against Stone's Throw is the same brand."""
    results = check_all(
        labelled(brand_name="STONE'S THROW"),
        ExpectedValues(brand_name="Stone's Throw"),
    )
    result = named(results, "brand")
    assert result.status is Status.REVIEW
    assert result.expected == "Stone's Throw" and result.observed == "STONE'S THROW"


def test_mch_02_exact_match_passes_outright():
    results = check_all(labelled(), ExpectedValues(brand_name="OLD TOM DISTILLERY"))
    assert named(results, "brand").status is Status.PASS


def test_mch_02_genuinely_different_name_fails():
    results = check_all(labelled(), ExpectedValues(brand_name="YOUNG TOM DISTILLERY"))
    assert named(results, "brand").status is Status.FAIL


def test_mch_02_missing_on_label_fails():
    results = check_all(labelled(brand_name=""), ExpectedValues(brand_name="OLD TOM"))
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


# --- MCH-03 — ABV tolerance ---------------------------------------------------


@pytest.mark.parametrize(
    "label_abv,expected_abv,status",
    [
        (45.0, 45.0, Status.PASS),  # identical
        (45.2, 45.0, Status.PASS),  # inside tolerance
        (44.7, 45.0, Status.PASS),  # inside tolerance, below
        (45.3, 45.0, Status.PASS),  # exactly at tolerance
        (45.4, 45.0, Status.FAIL),  # outside tolerance
        (40.0, 45.0, Status.FAIL),  # plainly different
    ],
)
def test_mch_03_tolerance_is_plus_or_minus_point_three(label_abv, expected_abv, status):
    """27 CFR 5.65(c) permits ±0.3 percentage points."""
    results = check_all(labelled(alcohol_content_pct=label_abv), ExpectedValues(alcohol_content_pct=expected_abv))
    assert named(results, "alcohol").status is status


def test_mch_03_quantifies_the_difference():
    results = check_all(labelled(alcohol_content_pct=46.0), ExpectedValues(alcohol_content_pct=45.0))
    assert "1 points" in named(results, "alcohol").detail


def test_mch_03_missing_label_abv_fails():
    results = check_all(labelled(alcohol_content_pct=None), ExpectedValues(alcohol_content_pct=45.0))
    assert named(results, "alcohol").status is Status.FAIL


# --- net contents compared by value ------------------------------------------


@pytest.mark.parametrize(
    "label_text,app_text,status",
    [
        ("750 mL", "750 mL", Status.PASS),
        ("750ML", "750 mL", Status.PASS),  # formatting only
        ("0.75 L", "750 mL", Status.PASS),  # different unit, same volume
        ("375 mL", "750 mL", Status.FAIL),
    ],
)
def test_net_contents_compared_by_volume_not_string(label_text, app_text, status):
    results = check_all(labelled(net_contents_raw=label_text), ExpectedValues(net_contents=app_text))
    assert named(results, "net contents").status is status


# --- MCH-05 — every finding shows both sides ---------------------------------


def test_every_non_passing_result_shows_expected_and_observed():
    results = check_all(
        labelled(brand_name="STONE'S THROW", alcohol_content_pct=40.0),
        ExpectedValues(brand_name="Stone's Throw", alcohol_content_pct=45.0),
    )
    for check in results:
        if check.status is not Status.PASS:
            assert check.expected and check.observed, f"{check.name} hides one side"

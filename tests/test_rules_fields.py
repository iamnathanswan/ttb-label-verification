"""Mandatory field rule tests — VAL-10..14. No network."""

import pytest

from app.models import LabelFields, Status
from app.rules.fields import check_all


def spirits(**overrides) -> LabelFields:
    """A distilled spirits label satisfying every field rule, before overrides."""
    base = dict(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content_pct=45.0,
        alcohol_content_proof=90.0,
        net_contents_raw="750 mL",
        producer_name="OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
        producer_function_phrase="BOTTLED BY",
        same_field_of_vision="yes",
    )
    return LabelFields(**{**base, **overrides})


def check(fields: LabelFields, check_id: str):
    matches = [c for c in check_all(fields) if c.id == check_id]
    assert matches, f"no check produced for {check_id}"
    return matches


# --- VAL-11 — alcohol content -------------------------------------------------


def test_val_11_percent_by_volume_passes():
    assert check(spirits(), "VAL-11")[0].status is Status.PASS


def test_val_11_proof_alone_fails():
    """§5.65: proof may accompany percent by volume but never replace it."""
    result = check(spirits(alcohol_content_pct=None), "VAL-11")[0]
    assert result.status is Status.FAIL
    assert "proof" in result.detail.lower()


def test_val_11_absent_fails():
    result = check(spirits(alcohol_content_pct=None, alcohol_content_proof=None), "VAL-11")[0]
    assert result.status is Status.FAIL


# --- VAL-12 — producer function phrase ---------------------------------------


@pytest.mark.parametrize("phrase", ["BOTTLED BY", "distilled by", "Imported By", "produced by"])
def test_val_12_recognised_phrases_pass(phrase):
    assert check(spirits(producer_function_phrase=phrase), "VAL-12")[0].status is Status.PASS


def test_val_12_missing_phrase_fails():
    result = check(spirits(producer_function_phrase=""), "VAL-12")[0]
    assert result.status is Status.FAIL
    assert "bottled by" in result.detail.lower()


def test_val_12_unrecognised_phrase_goes_to_review_not_fail():
    """An unfamiliar but plausible phrase is a judgement call, not a rejection."""
    assert check(spirits(producer_function_phrase="crafted by"), "VAL-12")[0].status is Status.REVIEW


def test_val_12_without_producer_name_cannot_be_assessed():
    assert check(spirits(producer_name="", producer_function_phrase=""), "VAL-12")[0].status is Status.REVIEW


# --- VAL-13 — country of origin ----------------------------------------------


def test_val_13_domestic_product_not_applicable():
    result = check(spirits(), "VAL-13")[0]
    assert result.status is Status.PASS
    assert "Not applicable" in result.detail


def test_val_13_import_without_country_fails():
    result = check(spirits(producer_function_phrase="IMPORTED BY", country_of_origin=""), "VAL-13")[0]
    assert result.status is Status.FAIL


def test_val_13_import_with_country_passes():
    result = check(spirits(producer_function_phrase="IMPORTED BY", country_of_origin="Scotland"), "VAL-13")[0]
    assert result.status is Status.PASS


# --- VAL-10 — field of vision -------------------------------------------------


def test_val_10_reports_observation():
    assert check(spirits(same_field_of_vision="no"), "VAL-10")[0].status is Status.FAIL
    assert check(spirits(same_field_of_vision="unclear"), "VAL-10")[0].status is Status.REVIEW


# --- VAL-14 — mandatory fields reported individually -------------------------


def test_val_14_all_present_pass():
    assert all(c.status is Status.PASS for c in check(spirits(), "VAL-14"))


def test_val_14_each_absence_reported_separately():
    """Four missing fields must produce four findings, not one aggregate failure."""
    bare = spirits(brand_name="", class_type="", net_contents_raw="", producer_name="")
    failures = [c for c in check(bare, "VAL-14") if c.status is Status.FAIL]
    assert len(failures) == 4
    named = " ".join(c.name for c in failures).lower()
    for expected in ("brand name", "class/type", "net contents", "producer"):
        assert expected in named


def test_val_14_citations_present_on_every_check():
    """A finding an agent cannot trace to a regulation is not actionable."""
    assert all(c.citation for c in check_all(spirits()))

"""Pairing labels to applications. No network."""

from app.models import ApplicationFields, PairingRule
from app.pairing import Candidate, pair


def app(filename: str, *, serial: str = "", brand: str = "") -> Candidate:
    return Candidate(filename, ApplicationFields(serial_number=serial, brand_name=brand))


def rule_for(outcome, label: str) -> PairingRule:
    return next(p.info.rule for p in outcome.pairs if p.label_filename == label)


# --- the single review --------------------------------------------------------

def test_one_of_each_pairs_directly():
    outcome = pair(["bourbon.png"], [app("cola.pdf", serial="24-0417")])
    assert rule_for(outcome, "bourbon.png") is PairingRule.SOLE_PAIR
    assert outcome.pairs[0].info.serial_number == "24-0417"


def test_a_label_with_no_application_is_still_checked():
    """Compliance must not regress when only a label is supplied."""
    outcome = pair(["bourbon.png"], [])
    assert rule_for(outcome, "bourbon.png") is PairingRule.UNPAIRED
    assert "only the regulations" in outcome.pairs[0].info.detail.lower()


# --- batch strategies ---------------------------------------------------------

def test_serial_in_the_label_filename_pairs():
    outcome = pair(
        ["24-0417-front.png", "24-0418-front.png"],
        [app("a.pdf", serial="24-0418"), app("b.pdf", serial="24-0417")],
    )
    assert rule_for(outcome, "24-0417-front.png") is PairingRule.SERIAL_IN_FILENAME
    assert next(p for p in outcome.pairs if p.label_filename == "24-0417-front.png").application.filename == "b.pdf"


def test_shared_filename_stem_pairs():
    outcome = pair(["bourbon.png", "gin.png"], [app("gin.pdf"), app("bourbon.pdf")])
    assert rule_for(outcome, "bourbon.png") is PairingRule.SHARED_FILENAME_STEM


def test_brand_name_pairs_when_unambiguous():
    outcome = pair(
        ["old-tom-distillery-label.png", "other.png"],
        [app("x.pdf", brand="Old Tom Distillery"), app("y.pdf", brand="Glen Castle")],
    )
    assert rule_for(outcome, "old-tom-distillery-label.png") is PairingRule.BRAND_NAME


def test_ambiguous_brand_is_a_question_not_a_pair():
    """Two applications sharing a brand must not be guessed between."""
    outcome = pair(
        ["old-tom-label.png"],
        [app("a.pdf", brand="Old Tom"), app("b.pdf", brand="Old Tom")],
    )
    assert rule_for(outcome, "old-tom-label.png") is PairingRule.UNPAIRED
    assert "could not be determined" in outcome.pairs[0].info.detail


def test_an_application_is_never_used_twice():
    outcome = pair(["bourbon.png", "bourbon-back.png"], [app("bourbon.pdf")])
    used = [p for p in outcome.pairs if p.application is not None]
    assert len(used) == 1


def test_unmatched_applications_are_reported_not_discarded():
    outcome = pair(["bourbon.png"], [app("bourbon.pdf"), app("orphan.pdf", serial="24-0423")])
    assert [c.filename for c in outcome.unused_applications] == ["orphan.pdf"]


def test_every_label_gets_an_outcome():
    """Nothing may be silently dropped from a 300-label batch."""
    labels = [f"label-{i}.png" for i in range(20)]
    outcome = pair(labels, [app("only.pdf", serial="24-0001")])
    assert {p.label_filename for p in outcome.pairs} == set(labels)


def test_unpaired_results_explain_how_to_fix_it():
    outcome = pair(["mystery.png", "other.png"], [app("a.pdf", serial="24-0001")])
    unpaired = next(p for p in outcome.pairs if p.info.rule is PairingRule.UNPAIRED)
    assert "serial number" in unpaired.info.detail.lower()

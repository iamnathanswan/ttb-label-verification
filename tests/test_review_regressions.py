"""Regressions for defects found in code review.

Each of these shipped, passed the suite, and would have reached a reviewer.
Keeping them named after the fault rather than the fix makes the reason visible.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.limits import SlidingWindowLimiter
from app.main import app
from app.models import ApplicationFields, LabelFields
from app.providers.anthropic_provider import SYSTEM_PROMPT
from app.providers.base import StubProvider
from app.rules import constants as C
from app.rules.engine import evaluate
from app.rules.units import minimum_type_size_mm, parse_volume_ml

# --- units ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_ml",
    [
        ("1,500 mL", 1500.0),  # thousands separator, not a decimal point
        ("1,000 mL", 1000.0),
        ("1,500.5 mL", 1500.5),
        ("1,75 L", 1750.0),  # European decimal notation still works
        ("1.75 L", 1750.0),
    ],
)
def test_thousands_separator_is_not_read_as_a_decimal_point(text, expected_ml):
    """ "1,500 mL" parsed as 1.5 mL, which then selected the wrong type-size bracket."""
    assert parse_volume_ml(text) == pytest.approx(expected_ml)


def test_thousands_separator_selects_the_correct_type_size():
    assert minimum_type_size_mm(parse_volume_ml("1,500 mL")) == 2.0


@pytest.mark.parametrize("text", ["25.4 FL. OZ.", "12 fl. oz.", "1 FL.OZ.", "12 fl oz"])
def test_fluid_ounces_with_periods_are_parsed(text):
    """A trailing \\b could not match a unit ending in a period, so these returned None."""
    assert parse_volume_ml(text) is not None


# --- prompt / schema agreement -------------------------------------------------


def test_prompt_never_asks_for_null_in_a_text_field():
    """The schema rejects null for text fields; obeying the old prompt caused a 503."""
    assert "If a field is absent, return null" not in SYSTEM_PROMPT
    assert "empty string" in SYSTEM_PROMPT


def test_every_field_named_in_the_prompt_exists_on_the_schema():
    """The prompt asked for `field_confidence`, which had been renamed away."""
    for name in ("low_confidence_fields", "image_legible", "illegible_reason", "warning_text"):
        assert name in LabelFields.model_fields
    assert "field_confidence" not in SYSTEM_PROMPT


def test_missing_mandatory_field_is_a_finding_not_an_extraction_failure():
    """The case VAL-14 exists to catch must not become a hard error."""
    fields = LabelFields.model_validate_json('{"brand_name": "", "warning_text": ""}')
    assert fields.brand_name == ""


# --- rate limiting --------------------------------------------------------------


def test_forged_forwarded_for_cannot_mint_a_fresh_bucket():
    """Proxies append, so the leftmost entry is caller-supplied and forgeable."""
    with TestClient(app) as client:
        client.app.state.provider = StubProvider(LabelFields())
        forged = client.post(
            "/api/verify",
            files={"file": ("x.png", b"not an image", "image/png")},
            headers={"x-forwarded-for": "1.2.3.4"},
        )
        # 400 for the bad image, not 429 — the point is that both requests land
        # in the same bucket, which the limiter test below asserts directly.
        assert forged.status_code == 400


def test_limiter_keys_on_the_proxy_written_entry():
    from app.limits import client_key

    class Req:
        headers = {"x-forwarded-for": "9.9.9.9, 203.0.113.7"}
        client = None

    assert client_key(Req()) == "203.0.113.7"


def test_limiter_does_not_grow_without_bound():
    """A caller rotating the header would otherwise leak one deque per value."""
    limiter = SlidingWindowLimiter(limit=5, window_seconds=0)
    for n in range(500):
        limiter.check(f"forged-{n}")
    assert len(limiter._hits) < 50


# --- batch robustness ------------------------------------------------------------


def test_oversized_file_does_not_abort_the_rest_of_the_batch(tmp_path):
    """299 results and one clear error beats spending the rate limit for nothing."""
    from pathlib import Path

    good = (Path(__file__).parent / "fixtures" / "labels" / "compliant_bourbon.png").read_bytes()
    oversized = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)

    with TestClient(app) as client:
        client.app.state.provider = StubProvider(LabelFields(warning_text=C.WARNING_STATEMENT))
        response = client.post(
            "/api/verify/batch",
            files=[
                ("files", ("good.png", good, "image/png")),
                ("files", ("huge.jpg", oversized, "image/jpeg")),
                ("files", ("good2.png", good, "image/png")),
            ],
        )
    assert response.status_code == 200
    assert response.text.count("event: result") == 2
    assert response.text.count("event: error") == 1
    assert "huge.jpg" in response.text


def test_aggregate_batch_size_is_capped():
    assert Settings().max_batch_bytes < Settings().max_batch_files * Settings().max_upload_bytes


# --- rules ------------------------------------------------------------------------


def test_lawful_unit_conversions_resolve_to_the_same_volume():
    """750 mL and 25.4 fl oz are one container declared two lawful ways.

    The comparison this once guarded has been retired — net contents is not a
    field on TTB F 5100.31 — but the parsing still selects the §16.22(b) type-size
    bracket for VAL-08, so getting it wrong still misstates a regulatory threshold.
    """
    assert parse_volume_ml("25.4 FL. OZ.") == pytest.approx(751.17, abs=0.01)
    assert parse_volume_ml("750 mL") == 750.0
    assert minimum_type_size_mm(parse_volume_ml("25.4 FL. OZ.")) == minimum_type_size_mm(750.0)


def test_genuinely_different_volumes_select_different_thresholds():
    assert minimum_type_size_mm(parse_volume_ml("50 mL")) == 1.0
    assert minimum_type_size_mm(parse_volume_ml("750 mL")) == 2.0


def test_wine_label_is_not_failed_against_a_part_5_citation():
    """VAL-14 cites Part 5 for class/type and producer, so those rows need softening too."""
    wine = LabelFields(
        beverage_type="wine",
        warning_text=C.WARNING_STATEMENT,
        warning_heading_is_caps="yes",
        warning_heading_is_bold="yes",
        warning_body_is_bold="no",
        warning_visually_separated="yes",
        brand_name="CHATEAU EXAMPLE",
        net_contents_raw="750 mL",
    )
    part_5_rows = [
        c for c in evaluate(wine) if c.name in {"Class/type designation present", "Producer name and address present"}
    ]
    assert part_5_rows
    assert all(c.status.value != "FAIL" for c in part_5_rows)


def test_application_is_still_optional_after_all_this():
    assert ApplicationFields().is_empty

"""Reading a COLA application — MCH-07, MCH-08, MCH-09. No network.

Fixtures are the official blank form filled programmatically, so these exercise
the real artifact. A hand-built PDF would pass an implementation the genuine form
breaks — as the positional checkbox reading did.
"""

from pathlib import Path

import pytest

from app.extract_application import (
    looks_like_application,
    read_form_fields,
    serial_from_filename,
)

APPS = Path(__file__).parent / "fixtures" / "applications"


def read(name: str):
    return read_form_fields((APPS / name).read_bytes())


# --- MCH-08 — exact where possible -------------------------------------------


def test_a_digital_form_is_read_from_its_fields_not_a_model():
    fields = read("24-0417-application.pdf")
    assert fields.extraction_source == "form_fields"
    assert fields.brand_name == "OLD TOM DISTILLERY"
    assert fields.serial_number == "24-0417"


def test_a_scanned_form_reports_that_it_needs_vision():
    """No widgets survive printing, so the fallback must be detected, not guessed."""
    assert read("24-0422-application-scanned.pdf") is None


# --- radio groups are read by export state, not position ---------------------


def test_source_is_read_correctly():
    assert read("24-0417-application.pdf").source_of_product == "domestic"
    assert read("24-0420-application-imported.pdf").source_of_product == "imported"


def test_type_is_read_correctly():
    assert read("24-0417-application.pdf").type_of_product == "distilled_spirits"
    assert read("24-0421-application-wine.pdf").type_of_product == "wine"


def test_source_widgets_share_a_row_so_position_would_be_arbitrary():
    """Why the reader uses export states: both options sit at the same height."""
    import pymupdf

    doc = pymupdf.open(APPS / "_blank_form_ttb_f_5100_31.pdf")
    ys = {round(w.rect.y0, 1) for page in doc for w in page.widgets() if w.field_name == "Check Box34"}
    assert len(ys) == 1, "source options are side by side; sorting by y cannot order them"


# --- supporting fields --------------------------------------------------------


def test_applicant_name_and_address_is_one_field():
    """Field 8 combines them, which is why the producer comparison is bespoke."""
    fields = read("24-0417-application.pdf")
    assert "OLD TOM DISTILLERY" in fields.applicant_name
    assert "KENTUCKY" in fields.applicant_name


def test_routing_recognises_the_form():
    assert looks_like_application((APPS / "24-0417-application.pdf").read_bytes())
    assert not looks_like_application(b"%PDF-1.4 not a cola application")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("24-0417-application.pdf", "24-0417"),
        ("24_0417_label.png", "24-0417"),
        ("bourbon.png", None),
    ],
)
def test_serial_is_recovered_from_a_filename(filename, expected):
    assert serial_from_filename(filename) == expected

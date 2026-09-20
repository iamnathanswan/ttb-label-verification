"""API tests — BAT-01, BAT-03, MCH-01, MCH-06, UX-07, OPS-05.

A StubProvider stands in for the model, so the suite needs no network and no key.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import LabelFields, Status
from app.providers.base import ExtractionError, StubProvider
from app.rules import constants as C

LABELS = Path(__file__).parent / "fixtures" / "labels"
APPLICATIONS = Path(__file__).parent / "fixtures" / "applications"


def compliant_fields(**overrides) -> LabelFields:
    base = dict(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content_pct=45.0,
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


@pytest.fixture
def client(monkeypatch):
    """A client whose provider always returns a compliant reading."""
    with TestClient(app) as c:
        c.app.state.provider = StubProvider(compliant_fields())
        yield c


@pytest.fixture
def label_bytes() -> bytes:
    return (LABELS / "compliant_bourbon.png").read_bytes()


@pytest.fixture
def application_bytes() -> bytes:
    return (APPLICATIONS / "24-0417-application.pdf").read_bytes()


def test_health_reports_extraction_configuration(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "extraction_configured" in body


def test_config_exposes_limits_the_ui_needs(client):
    body = client.get("/api/config").json()
    assert body["max_batch_files"] > 0 and body["max_upload_bytes"] > 0


# --- single label -------------------------------------------------------------


def test_verify_returns_checks_and_timing(client, label_bytes):
    r = client.post("/api/verify", files={"file": ("label.png", label_bytes, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == Status.PASS
    assert body["checks"] and body["filename"] == "label.png"
    assert body["elapsed_ms"] >= 0


def test_verify_without_application_values_skips_matching(client, label_bytes):
    body = client.post("/api/verify", files={"file": ("l.png", label_bytes, "image/png")}).json()
    assert not [c for c in body["checks"] if c["id"].startswith("MCH")]


def test_verify_with_an_application_adds_matching(client, label_bytes, application_bytes):
    """Both documents are uploaded; neither side is typed."""
    r = client.post(
        "/api/verify",
        files={
            "file": ("compliant_bourbon.png", label_bytes, "image/png"),
            "application": ("24-0417-application.pdf", application_bytes, "application/pdf"),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert [c for c in body["checks"] if c["id"].startswith("MCH")]
    assert body["application"]["brand_name"] == "OLD TOM DISTILLERY"
    assert body["application"]["extraction_source"] == "form_fields"
    assert body["pairing"]["rule"] == "sole_pair"


def test_case_difference_surfaces_as_review_not_failure(client, label_bytes):
    """Dave's case, end to end, with the brand read off a real application."""
    application = (APPLICATIONS / "24-0418-application-case-differs.pdf").read_bytes()
    r = client.post(
        "/api/verify",
        files={
            "file": ("compliant_bourbon.png", label_bytes, "image/png"),
            "application": ("24-0418-application-case-differs.pdf", application, "application/pdf"),
        },
    )
    brand = next(
        c for c in r.json()["checks"]
        if c["id"].startswith("MCH") and "brand" in c["name"].lower()
    )
    assert brand["status"] == Status.REVIEW
    assert brand["expected"] == "Old Tom Distillery"
    assert brand["observed"] == "OLD TOM DISTILLERY"


def test_serial_number_is_reported_so_pairing_can_be_audited(client, label_bytes, application_bytes):
    r = client.post(
        "/api/verify",
        files={
            "file": ("compliant_bourbon.png", label_bytes, "image/png"),
            "application": ("24-0417-application.pdf", application_bytes, "application/pdf"),
        },
    )
    assert r.json()["pairing"]["serial_number"] == "24-0417"


def test_a_label_alone_still_runs_compliance(client, label_bytes):
    """The single-document path must not regress now that two are accepted."""
    body = client.post(
        "/api/verify", files={"file": ("l.png", label_bytes, "image/png")}
    ).json()
    assert body["application"] is None
    assert [c for c in body["checks"] if c["id"].startswith("VAL")]
    assert not [c for c in body["checks"] if c["id"].startswith("MCH")]


def test_unreadable_upload_is_rejected_with_a_usable_message(client):
    r = client.post("/api/verify", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400
    assert "supported" in r.json()["detail"].lower()


def test_extraction_failure_maps_to_a_retryable_status(client, label_bytes):
    client.app.state.provider = StubProvider(error=ExtractionError("busy", retryable=True))
    r = client.post("/api/verify", files={"file": ("l.png", label_bytes, "image/png")})
    assert r.status_code == 503


# --- batch --------------------------------------------------------------------


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines and "data" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_batch_streams_one_result_per_label(client, label_bytes):
    files = [("files", (f"l{i}.png", label_bytes, "image/png")) for i in range(3)]
    r = client.post("/api/verify/batch", files=files)
    assert r.status_code == 200
    events = _events(r.text)
    assert events[0][0] == "start" and events[0][1]["total"] == 3
    assert len([e for e in events if e[0] == "result"]) == 3
    assert events[-1][0] == "done"


def test_batch_reports_progress_on_every_event(client, label_bytes):
    files = [("files", (f"l{i}.png", label_bytes, "image/png")) for i in range(2)]
    events = _events(client.post("/api/verify/batch", files=files).text)
    for name, payload in events:
        if name in {"result", "error"}:
            assert payload["progress"]["total"] == 2


def test_one_bad_label_does_not_abort_the_batch(client, label_bytes):
    """BAT-04 — 299 results and one clear error beats nothing at all."""
    files = [
        ("files", ("good.png", label_bytes, "image/png")),
        ("files", ("bad.png", b"garbage", "image/png")),
        ("files", ("good2.png", label_bytes, "image/png")),
    ]
    events = _events(client.post("/api/verify/batch", files=files).text)
    assert len([e for e in events if e[0] == "result"]) == 2
    errors = [e for e in events if e[0] == "error"]
    assert len(errors) == 1 and errors[0][1]["filename"] == "bad.png"


def test_batch_pairs_applications_to_labels(client, label_bytes):
    """A batch takes both sets of documents and reports how each was paired."""
    application = (APPLICATIONS / "24-0417-application.pdf").read_bytes()
    files = [
        ("files", ("24-0417-label.png", label_bytes, "image/png")),
        ("applications", ("24-0417-application.pdf", application, "application/pdf")),
    ]
    events = _events(client.post("/api/verify/batch", files=files).text)
    result = next(p for n, p in events if n == "result")
    assert result["pairing"]["rule"] in {"sole_pair", "serial_in_filename"}
    assert result["application"]["serial_number"] == "24-0417"


def test_an_application_with_no_label_is_reported(client, label_bytes):
    """An orphan must be surfaced, never silently discarded."""
    orphan = (APPLICATIONS / "24-0423-application-orphan.pdf").read_bytes()
    files = [
        ("files", ("bourbon.png", label_bytes, "image/png")),
        ("applications", ("bourbon.pdf", (APPLICATIONS / "24-0417-application.pdf").read_bytes(), "application/pdf")),
        ("applications", ("24-0423-application-orphan.pdf", orphan, "application/pdf")),
    ]
    text = client.post("/api/verify/batch", files=files).text
    assert "24-0423-application-orphan.pdf" in text
    assert "No label matched this application" in text


def test_batch_over_the_file_ceiling_is_refused(client, label_bytes, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_batch_files", 2)
    files = [("files", (f"l{i}.png", label_bytes, "image/png")) for i in range(3)]
    r = client.post("/api/verify/batch", files=files)
    assert r.status_code == 413
    assert "limit is 2" in r.json()["detail"]

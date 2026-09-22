"""OPS-07 — executable content is removed before a document is displayed.

The fixtures are generated from the real TTB F 5100.31, which carries a
document-level script, so they exercise the actual case rather than a contrived
one. That is deliberate: the fixtures are left un-sanitised on disk precisely so
these tests have something real to strip.
"""

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.ingest import UnsupportedUpload
from app.main import app
from app.sanitize import strip_active_content

APPLICATIONS = Path(__file__).parent / "fixtures" / "applications"
FORM = APPLICATIONS / "24-0417-application.pdf"


@pytest.fixture(scope="module")
def raw() -> bytes:
    return FORM.read_bytes()


@pytest.fixture(scope="module")
def clean(raw: bytes) -> bytes:
    return strip_active_content(raw)


def scripts(data: bytes) -> list[str]:
    """Every JavaScript body the document carries, decompressed.

    Searching the raw bytes is not enough and quietly proves nothing: the form's
    document-level script lives in a Flate stream, so `b"app.alert" in pdf` is
    False even for the untouched original.
    """
    doc = pymupdf.open(stream=data, filetype="pdf")
    found: list[str] = []
    try:
        for xref in range(1, doc.xref_length()):
            obj = doc.xref_object(xref, compressed=True)
            if "/S/JavaScript" in obj or "/JavaScript" in obj:
                found.append(obj)
            if doc.xref_is_stream(xref):
                try:
                    body = doc.xref_stream(xref)
                except Exception:
                    continue
                text = body.decode("latin-1", "replace")
                if "app.alert" in text or "function init" in text:
                    found.append(text)
    finally:
        doc.close()
    return found


def test_ops_07_fixture_really_does_carry_a_script(raw: bytes) -> None:
    """Guard the guard. If a form revision drops the script, the tests below stop
    proving anything, and should say so rather than passing vacuously."""
    assert any("app.alert" in s for s in scripts(raw)), "fixture no longer carries the alert"


def test_ops_07_document_level_script_is_removed(clean: bytes) -> None:
    assert not any("app.alert" in s for s in scripts(clean))
    # The alert text itself, which is what a reviewer was seeing.
    assert not any("LEGAL" in s for s in scripts(clean))


def test_ops_07_no_script_body_survives(clean: bytes) -> None:
    doc = pymupdf.open(stream=clean, filetype="pdf")
    try:
        bodies = [
            doc.xref_object(xref, compressed=True)
            for xref in range(1, doc.xref_length())
            if "/S/JavaScript" in doc.xref_object(xref, compressed=True)
        ]
    finally:
        doc.close()
    assert all("/JS()" in body for body in bodies), bodies


def test_ops_07_field_values_are_preserved(raw: bytes, clean: bytes) -> None:
    """The reviewer opened the form to read what was declared on it."""

    def values(data: bytes) -> dict[str, str]:
        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            return {w.field_name: w.field_value for page in doc for w in page.widgets()}
        finally:
            doc.close()

    before = values(raw)
    assert sum(1 for v in before.values() if v) > 10, "fixture should be filled in"
    assert values(clean) == before


def test_ops_07_pages_are_preserved(raw: bytes, clean: bytes) -> None:
    def pages(data: bytes) -> int:
        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            return doc.page_count
        finally:
            doc.close()

    assert pages(clean) == pages(raw)


def test_ops_07_output_is_still_a_readable_pdf(clean: bytes) -> None:
    assert clean[:4] == b"%PDF"
    doc = pymupdf.open(stream=clean, filetype="pdf")
    try:
        assert doc.page_count > 0
        assert doc.load_page(0).get_text().strip()
    finally:
        doc.close()


def test_ops_07_rejects_a_non_pdf() -> None:
    with pytest.raises(UnsupportedUpload):
        strip_active_content(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


def test_ops_07_endpoint_returns_a_sanitised_pdf(raw: bytes) -> None:
    with TestClient(app) as client:
        response = client.post("/api/document", files={"file": ("application.pdf", raw, "application/pdf")})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert not any("app.alert" in s for s in scripts(response.content))


def test_ops_07_endpoint_is_sandboxed(raw: bytes) -> None:
    """The browser must not run the response as a document of our own origin."""
    with TestClient(app) as client:
        response = client.post("/api/document", files={"file": ("a.pdf", raw, "application/pdf")})
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_ops_07_endpoint_rejects_an_image() -> None:
    with TestClient(app) as client:
        response = client.post("/api/document", files={"file": ("label.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    assert response.status_code == 400


def test_ops_07_endpoint_is_outside_the_rate_limit(raw: bytes) -> None:
    """Looking at your own documents must not exhaust the budget for checking them."""
    with TestClient(app) as client:
        for _ in range(12):
            assert client.post("/api/document", files={"file": ("a.pdf", raw, "application/pdf")}).status_code == 200

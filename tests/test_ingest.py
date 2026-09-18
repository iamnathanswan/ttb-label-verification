"""Upload handling — EXT-09, EXT-10, PRF-04. No network."""

import io

import pymupdf
import pytest
from PIL import Image

from app.config import settings
from app.ingest import UnsupportedUpload, prepare


def png(width: int, height: int, mode: str = "RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


# --- EXT-10 — accepted formats ------------------------------------------------

@pytest.mark.parametrize("fmt,media", [
    ("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("TIFF", "image/tiff"),
])
def test_ext_10_common_image_formats_are_accepted(fmt, media):
    buf = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(buf, format=fmt)
    image, out_media = prepare(buf.getvalue())
    assert out_media == "image/jpeg" and image


def test_ext_10_pdf_first_page_is_rendered():
    """COLA submissions are frequently PDFs, with the label on page one."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "OLD TOM DISTILLERY", fontsize=24)
    image, media = prepare(doc.tobytes())
    assert media == "image/jpeg"
    assert Image.open(io.BytesIO(image)).size[0] > 0


def test_ext_10_format_is_detected_from_content_not_filename():
    """A mislabelled extension must not decide how bytes are parsed."""
    with pytest.raises(UnsupportedUpload, match="not a supported image"):
        prepare(b"<html>definitely not a label</html>")


def test_ext_10_empty_upload_is_refused():
    with pytest.raises(UnsupportedUpload, match="empty"):
        prepare(b"")


def test_ext_10_oversized_upload_is_refused_before_decoding():
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (settings.max_upload_bytes + 1)
    with pytest.raises(UnsupportedUpload, match="larger than"):
        prepare(oversized)


# --- PRF-04 — downscaling before the model call -------------------------------

def test_prf_04_large_images_are_downscaled_to_the_configured_edge():
    image, _ = prepare(png(4000, 3000))
    assert max(Image.open(io.BytesIO(image)).size) == settings.max_image_edge_px


def test_prf_04_small_images_are_not_upscaled():
    image, _ = prepare(png(800, 600))
    assert Image.open(io.BytesIO(image)).size == (800, 600)


def test_prf_04_aspect_ratio_is_preserved():
    """Distorting a label would corrupt the typography the rules depend on."""
    image, _ = prepare(png(4000, 2000))
    width, height = Image.open(io.BytesIO(image)).size
    assert abs((width / height) - 2.0) < 0.01


# --- EXT-09 — imperfect captures ----------------------------------------------

def test_ext_09_exif_rotation_is_normalised():
    """A phone photo carries rotation in metadata; the model sees pixels."""
    buf = io.BytesIO()
    img = Image.new("RGB", (1200, 800), "white")
    exif = img.getexif()
    exif[274] = 6  # orientation: rotate 90° clockwise
    img.save(buf, format="JPEG", exif=exif)
    image, _ = prepare(buf.getvalue())
    # Transposed, so the long edge moves from width to height.
    assert Image.open(io.BytesIO(image)).size == (800, 1200)


def test_ext_09_greyscale_and_paletted_images_are_handled():
    for mode in ("L", "P", "RGBA"):
        image, media = prepare(png(600, 800, mode))
        assert media == "image/jpeg" and image

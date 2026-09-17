"""Turn an upload into something the model can read cheaply (EXT-10, PRF-04).

Latency is a binding requirement (PRF-01) and image size is the largest lever we
control: a 4000px phone photo costs several times the tokens and upload time of a
1600px one, with no gain in legibility for label text.
"""

import io

import pymupdf
from PIL import Image, ImageOps

from app.config import settings

JPEG_QUALITY = 88
PDF_RENDER_DPI = 200

SUPPORTED = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/tiff",
    "application/pdf",
}


class UnsupportedUpload(Exception):
    """The upload is not a readable label image. Message is shown to the user (UX-07)."""


def _sniff(data: bytes) -> str:
    """Identify by magic bytes rather than trusting the filename."""
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] in (b"II", b"MM"):
        return "image/tiff"
    raise UnsupportedUpload("That file is not a supported image. Upload a JPEG, PNG, WebP, TIFF or PDF of the label.")


def _pdf_first_page(data: bytes) -> Image.Image:
    """Render page one. A COLA submission puts the label on the first page."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surfaced to the user, not swallowed
        raise UnsupportedUpload("That PDF could not be opened. It may be corrupt or password protected.") from exc
    if doc.page_count == 0:
        raise UnsupportedUpload("That PDF has no pages.")
    pix = doc.load_page(0).get_pixmap(dpi=PDF_RENDER_DPI)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def prepare(data: bytes, *, max_edge: int | None = None) -> tuple[bytes, str]:
    """Normalise an upload to a right-side-up, downscaled JPEG.

    Returns (jpeg_bytes, media_type) ready for the provider.

    Raises:
        UnsupportedUpload: unreadable or oversized input.
    """
    if not data:
        raise UnsupportedUpload("That file is empty.")
    if len(data) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise UnsupportedUpload(f"That file is larger than the {mb} MB limit. Upload a smaller image.")

    kind = _sniff(data)
    if kind not in SUPPORTED:
        raise UnsupportedUpload("That file type is not supported.")

    if kind == "application/pdf":
        img = _pdf_first_page(data)
    else:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as exc:  # noqa: BLE001
            raise UnsupportedUpload("That image could not be read. It may be corrupt.") from exc

    # Phone photos carry rotation in EXIF; the model sees pixels, not metadata.
    img = ImageOps.exif_transpose(img)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    limit = max_edge or settings.max_image_edge_px
    if max(img.size) > limit:
        img.thumbnail((limit, limit), Image.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), "image/jpeg"

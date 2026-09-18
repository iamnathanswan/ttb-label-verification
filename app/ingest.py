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

# A decompression bomb is a small file that decodes to an enormous raster: a 136 KB
# PNG can expand to 144 megapixels, which at 8 concurrent extractions is enough to
# exhaust a container. Pillow only warns about this by default, so the dimensions
# are checked from the header before any pixel data is decoded. A generous ceiling
# still admits a 50 MP photograph, far beyond any legible label image.
MAX_PIXELS = 50_000_000

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


def _guard_pixels(width: int, height: int) -> None:
    """Refuse rasters large enough to exhaust memory, before decoding them."""
    if width * height > MAX_PIXELS:
        raise UnsupportedUpload(
            f"That image is {width} by {height} pixels, which is too large to process. "
            "Upload a smaller image of the label."
        )


def _pdf_first_page(data: bytes) -> Image.Image:
    """Render page one. A COLA submission puts the label on the first page."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surfaced to the user, not swallowed
        raise UnsupportedUpload("That PDF could not be opened. It may be corrupt or password protected.") from exc
    if doc.page_count == 0:
        raise UnsupportedUpload("That PDF has no pages.")

    page = doc.load_page(0)
    # A page can declare any size; at a fixed DPI an outsized one rasterises
    # to an outsized bitmap, so the same ceiling applies before rendering.
    scale = PDF_RENDER_DPI / 72.0
    _guard_pixels(int(page.rect.width * scale), int(page.rect.height * scale))

    pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
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
        except Exception as exc:  # noqa: BLE001
            raise UnsupportedUpload("That image could not be read. It may be corrupt.") from exc

        # Image.open reads the header only; size is known before any pixels are
        # decoded, which is the point at which a bomb must be refused.
        _guard_pixels(*img.size)

        try:
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

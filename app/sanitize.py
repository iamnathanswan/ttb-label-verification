"""Strip executable content from a PDF before a browser is asked to display it (OPS-07).

PDF is not a passive format. A document can carry JavaScript that a viewer runs on
open, and every mainstream viewer — Chrome's PDFium, Firefox's pdf.js, Acrobat —
executes it by default with no prompt.

TTB F 5100.31 is itself an example. The official form carries a document-level
script that fires an alert on open:

    app.alert("Please set page size to LEGAL in Page Setup before Printing...")

Harmless, and genuinely confusing when it appears over a compliance tool that never
mentioned printing. But the same mechanism in a document from outside is not
harmless, and this tool exists to open documents from outside. Whatever an
applicant attaches gets rendered in a reviewer's browser, so it is sanitised on the
way there rather than trusted.

Field values are preserved. The reviewer is looking at the form to check what was
declared, so blanking the fields would defeat the purpose of showing it at all.
"""

import pymupdf

from app.ingest import UnsupportedUpload

# Everything scrub() can remove, enumerated rather than defaulted. The defaults
# also reset form fields and strip metadata, which would empty the very values the
# reviewer opened the document to read.
_SCRUB = {
    "javascript": True,
    "attached_files": True,
    "embedded_files": True,
    "remove_links": True,
    "metadata": False,
    "clean_pages": False,
    "hidden_text": False,
    "redactions": False,
    "reset_fields": False,
    "reset_responses": False,
    "thumbnails": False,
    "xml_metadata": False,
}


def _drop_document_javascript(doc: pymupdf.Document) -> None:
    """Unhook the document-level script name tree from the catalogue.

    scrub() empties each script body, which is already enough to make them inert,
    but leaves /Names /JavaScript pointing at the emptied objects. Clearing the
    entry means an auditor reading the file does not have to take our word for the
    bodies being blank.

    The catalogue reaches the tree through an indirect reference, and writing a key
    through a path that crosses one leaves a PyMuPDF placeholder rather than the
    value asked for. So the /Names dictionary is resolved and edited directly.
    """
    kind, value = doc.xref_get_key(doc.pdf_catalog(), "Names")
    if kind != "xref":
        return
    doc.xref_set_key(int(value.split()[0]), "JavaScript", "null")


def strip_active_content(data: bytes) -> bytes:
    """Return the PDF with scripts, attachments and link actions removed.

    Raises UnsupportedUpload if the bytes are not a readable PDF.
    """
    if data[:4] != b"%PDF":
        raise UnsupportedUpload("That file is not a PDF.")

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf raises several unrelated types on bad input
        raise UnsupportedUpload("That PDF could not be read.") from exc

    try:
        doc.scrub(**_SCRUB)
        _drop_document_javascript(doc)
        doc.xref_set_key(doc.pdf_catalog(), "OpenAction", "null")
        doc.xref_set_key(doc.pdf_catalog(), "AA", "null")
        return doc.tobytes(deflate=True, garbage=4)
    finally:
        doc.close()

"""Read a COLA application — TTB F 5100.31.

Two paths, and which one ran is reported to the agent.

A form completed digitally is an AcroForm: the values live in widgets and can be
read exactly, with no model and no inference. A form that was printed, signed and
scanned has no widgets, and has to be read as an image like a label.

Reading the digital case exactly is the point of the feature. The interviews
describe agents "drowning" in data entry verification; a comparison built on
inference on both sides would replace that with a different kind of doubt.
"""

import re

import pymupdf

from app.models import ApplicationFields, BeverageType, SourceOfProduct

# Widget names on the current form (OMB No. 1513-0020). Exact, including the
# double spaces the form itself contains.
FIELD_BRAND = "6. BRAND NAME (Required)"
FIELD_FANCIFUL = "7. FANCIFUL NAME (If any)"
FIELD_APPLICANT = "8. NAME AND ADDRESS OF APPLICANT AS SHOWN ON PLANT REGISTRY, BASIC"
FIELD_PERMIT = "2.  PLANT REGISTRY/BASIC PERMIT/BREWER'S NO. (Required)"
FIELD_TTB_ID = "TTB ID"
SERIAL_PARTS = ("YEAR 1", "YEAR 2", "SERIAL NUMBER 1", "SERIAL NUMBER 2", "SERIAL NUMBER 3", "SERIAL NUMBER 4")

# Source (field 3) and type (field 5) are radio groups: several widgets sharing one
# field name, where the selected option is identified by that widget's export state
# rather than by a boolean. The states are semantic, so they are read by name.
#
# Position would not work for source: both of its widgets sit at the same vertical
# coordinate, printed side by side, so sorting by y is arbitrary between them.
GROUP_SOURCE = "Check Box34"
GROUP_TYPE = "Check Box22"

SOURCE_STATES: dict[str, SourceOfProduct] = {"Domes": "domestic", "Import": "imported"}
TYPE_STATES: dict[str, BeverageType] = {
    "Wine": "wine",
    "Spirits": "distilled_spirits",
    "Malt": "malt_beverage",
}


class NotAnApplication(Exception):
    """The PDF is not a recognisable COLA application."""


def _selected(widgets: list, group: str, states: dict[str, str]) -> str | None:
    """Return the option selected in a radio group, by its export state.

    Every widget in the group reports the field's shared value; the selected one
    is whichever export state that value names. Unrecognised states return None
    rather than a guess — sending a label through the wrong Part of the CFR
    because a form revision renamed a state is worse than declining to decide.
    """
    for widget in widgets:
        if widget.field_name != group:
            continue
        value = (widget.field_value or "").strip()
        if value and value.lower() not in {"off", "no", "false"}:
            return states.get(value)
    return None


def _text(widgets: list, name: str) -> str:
    for widget in widgets:
        if widget.field_name == name:
            return (widget.field_value or "").strip()
    return ""


def _serial(widgets: list) -> str:
    """Assemble field 4 from its six boxes: two year digits, four serial digits."""
    parts = [_text(widgets, name) for name in SERIAL_PARTS]
    year = "".join(parts[:2]).strip()
    serial = "".join(parts[2:]).strip()
    if year and serial:
        return f"{year}-{serial}"
    return serial or year


def read_form_fields(pdf_bytes: bytes) -> ApplicationFields | None:
    """Read an AcroForm application exactly. None when the PDF carries no widgets."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surfaced to the user
        raise NotAnApplication("That PDF could not be opened. It may be corrupt or password protected.") from exc

    widgets = [w for page in doc for w in page.widgets()]
    if not widgets:
        return None

    fields = ApplicationFields(
        serial_number=_serial(widgets),
        permit_number=_text(widgets, FIELD_PERMIT),
        source_of_product=_selected(widgets, GROUP_SOURCE, SOURCE_STATES),
        type_of_product=_selected(widgets, GROUP_TYPE, TYPE_STATES),
        brand_name=_text(widgets, FIELD_BRAND),
        fanciful_name=_text(widgets, FIELD_FANCIFUL),
        applicant_name=" ".join(_text(widgets, FIELD_APPLICANT).split()),
        ttb_id=_text(widgets, FIELD_TTB_ID),
        extraction_source="form_fields",
    )
    return None if fields.is_empty else fields


def looks_like_application(pdf_bytes: bytes) -> bool:
    """Cheap check used to route an upload to the application side of the form."""
    head = pdf_bytes[:4]
    if head != b"%PDF":
        return False
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text = doc.load_page(0).get_text().upper()
    except Exception:  # noqa: BLE001 — routing only; a failure here is not fatal
        return False
    return "LABEL/BOTTLE APPROVAL" in text or "TTB F 5100.31" in text


SERIAL_PATTERN = re.compile(r"\b(\d{2})[-_ ]?(\d{3,6})\b")


def serial_from_filename(filename: str) -> str | None:
    """Find a serial number in a filename, for pairing.

    The serial identifies the application but is never printed on the label — it is
    not a labelling requirement under Parts 4, 5, 7 or 16 — so it can only pair two
    documents by way of their filenames.
    """
    match = SERIAL_PATTERN.search(filename)
    return f"{match.group(1)}-{match.group(2)}" if match else None

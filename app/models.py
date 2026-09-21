"""Data contracts.

`LabelFields` is the boundary between the model and the rest of the system (D2).
It is both the extraction schema handed to the API and the input to every rule,
so the shape is declared exactly once.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class Status(StrEnum):
    """Three states, never a boolean (MCH-04).

    REVIEW is the honest answer when a requirement is met in substance but not in
    form, or when a photograph cannot supply the evidence a rule needs.
    """

    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


BeverageType = Literal["distilled_spirits", "wine", "malt_beverage", "unknown"]

Observation = Literal["yes", "no", "unclear"]
"""A three-valued visual judgement.

Deliberately not `bool | None`. "unclear" is a distinct, meaningful answer — the
photograph may simply not settle whether type is bold — and it maps directly onto
the REVIEW status rather than being silently treated as "no".
"""


class LabelFields(BaseModel):
    """What the model reads off the label. Transcription only — no judgement.

    Absent text is the empty string rather than null. The structured-output schema
    has a complexity budget, and nullable strings are unions that consume it fast;
    an empty string carries the same meaning ("not printed on this label") at a
    fraction of the schema cost. Rules test falsiness, so the distinction never
    reaches the regulatory logic.
    """

    # Mandatory information (EXT-01..06)
    brand_name: str = Field("", description="Brand name exactly as printed, else empty")
    class_type: str = Field("", description="Class/type designation, e.g. 'Kentucky Straight Bourbon Whiskey'")
    alcohol_content_pct: float | None = Field(None, description="Alcohol by volume as a number, e.g. 45.0")
    alcohol_content_proof: float | None = Field(None, description="Degrees proof if stated, else null")
    net_contents_raw: str = Field("", description="Net contents exactly as printed, e.g. '750 mL'")
    producer_name: str = Field("", description="Name of the bottler, distiller, or importer")
    producer_address: str = Field("", description="Address accompanying the producer name")
    producer_function_phrase: str = Field(
        "", description="Phrase preceding the producer name: 'bottled by', 'distilled by', 'imported by', etc."
    )
    country_of_origin: str = Field("", description="Country of origin if stated")

    # Government warning (EXT-07) — verbatim, never normalised
    warning_text: str = Field(
        "", description="The warning exactly as printed, preserving capitalisation, punctuation and numbering"
    )

    # Typographic and spatial observations the rules depend on
    warning_heading_is_caps: Observation = Field("unclear", description="Is 'GOVERNMENT WARNING' in capital letters?")
    warning_heading_is_bold: Observation = Field("unclear", description="Is 'GOVERNMENT WARNING' in bold type?")
    warning_body_is_bold: Observation = Field(
        "unclear", description="Is the text AFTER the heading bold? Judge independently of the heading."
    )
    warning_visually_separated: Observation = Field(
        "unclear", description="Is the warning set apart by a box, rule, or whitespace?"
    )
    warning_on_contrasting_background: Observation = Field(
        "unclear", description="Does the warning sit on a contrasting background?"
    )
    same_field_of_vision: Observation = Field(
        "unclear", description="Are brand name, class/type and alcohol content visible without turning the container?"
    )

    # Extraction metadata
    beverage_type: BeverageType = Field("unknown", description="Beverage category inferred from the label")
    image_legible: bool = Field(True, description="False only if the image genuinely cannot be read")
    illegible_reason: str = Field("", description="Why the image could not be read, if applicable")
    low_confidence_fields: list[str] = Field(
        default_factory=list, description="Names of any fields read with difficulty (EXT-08)"
    )


SourceOfProduct = Literal["domestic", "imported"]

ExtractionSource = Literal["form_fields", "vision"]
"""How an application was read.

`form_fields` means the values came straight out of the PDF's AcroForm widgets —
exact strings, no inference. `vision` means the form was scanned or flattened and
had to be read as an image. An agent should be told which, because the two carry
very different confidence.
"""


class ApplicationFields(BaseModel):
    """What the COLA application declares. TTB F 5100.31.

    The field set follows the current form. Two absences are deliberate:

    - **No class/type.** TTB instructs applicants not to supply the designation and
      returns applications that do, so there is nothing to compare against. The
      designation must still appear on the label; VAL-14 checks that.
    - **No net contents or alcohol content.** Both were removed from the form —
      field 15 asks for container wording only where it does *not* appear on the
      labels. TTB reads them off the label, and so do we (VAL-11, VAL-14, VAL-08).
    """

    serial_number: str = Field("", description="Field 4, assembled from year and serial boxes")
    permit_number: str = Field("", description="Field 2, plant registry / basic permit / brewer's number")
    source_of_product: SourceOfProduct | None = Field(None, description="Field 3")
    type_of_product: BeverageType | None = Field(None, description="Field 5")
    brand_name: str = Field("", description="Field 6")
    fanciful_name: str = Field("", description="Field 7")
    applicant_name: str = Field("", description="Field 8, name and address of applicant")
    ttb_id: str = Field("", description="TTB ID, where the form carries one")

    extraction_source: ExtractionSource = Field("form_fields")
    filename: str = Field("", description="The file this was read from")

    @property
    def is_empty(self) -> bool:
        """True when nothing usable was read — an unfilled or unreadable form."""
        return not any((self.brand_name, self.applicant_name, self.serial_number, self.source_of_product))


class PairingRule(StrEnum):
    """How a label was matched to an application. Reported on every result.

    An agent should never have to guess why two documents were treated as a pair.
    """

    SOLE_PAIR = "sole_pair"
    SERIAL_IN_FILENAME = "serial_in_filename"
    SHARED_FILENAME_STEM = "shared_filename_stem"
    BRAND_NAME = "brand_name"
    UNPAIRED = "unpaired"


class PairingInfo(BaseModel):
    rule: PairingRule
    application_filename: str | None = None
    serial_number: str | None = None
    detail: str = ""


CheckCategory = Literal["matching", "compliance", "extraction"]
"""Which question a finding answers.

Two different things are being asked, and an agent acts on them differently.
*Compliance* asks whether the label is lawful on its own terms — it is answered
from the label and the CFR alone. *Matching* asks whether the label agrees with
what was declared on the application, which is a question about two documents and
is often resolved by correcting the application rather than the label.

Keeping them apart matters because a label can match its application perfectly and
still be illegal, and can be perfectly lawful while disagreeing with the form.
"""


class CheckResult(BaseModel):
    """One rule, one outcome, one citation."""

    id: str = Field(description="Requirement ID, e.g. 'VAL-04'")
    name: str
    status: Status
    detail: str = Field(description="Plain-language explanation an agent can act on")
    citation: str | None = Field(None, description="e.g. '27 CFR 16.22(a)(2)'")
    expected: str | None = None
    observed: str | None = None
    advisory: bool = Field(False, description="True where a photograph cannot decide the rule (VAL-06..09)")

    @computed_field
    @property
    def category(self) -> CheckCategory:
        """Derived from the requirement ID, so it cannot drift from the rule."""
        return {"MCH": "matching", "EXT": "extraction"}.get(self.id[:3], "compliance")


class VerificationResult(BaseModel):
    overall: Status
    checks: list[CheckResult]
    fields: LabelFields
    application: ApplicationFields | None = Field(
        None, description="What the COLA application declared, when one was paired"
    )
    pairing: PairingInfo | None = Field(None, description="How the application was matched")
    elapsed_ms: int = Field(description="End-to-end wall time for this label (PRF-03)")
    filename: str | None = None
    usage: dict[str, int] = Field(default_factory=dict, description="Token usage, incl. cache hits")

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is Status.FAIL]

    @property
    def reviews(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is Status.REVIEW and not c.advisory]

    @property
    def advisories(self) -> list[CheckResult]:
        """Checks a photograph cannot decide. Constant across labels; shown, not scored."""
        return [c for c in self.checks if c.advisory]

    @property
    def compliance_checks(self) -> list[CheckResult]:
        """Is this label lawful on its own terms? Answered from the label and the CFR."""
        return [c for c in self.checks if not c.advisory and c.category != "matching"]

    @property
    def matching_checks(self) -> list[CheckResult]:
        """Does the label agree with the application? Empty when none was paired."""
        return [c for c in self.checks if not c.advisory and c.category == "matching"]

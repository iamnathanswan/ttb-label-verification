"""Data contracts.

`LabelFields` is the boundary between the model and the rest of the system (D2).
It is both the extraction schema handed to the API and the input to every rule,
so the shape is declared exactly once.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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


class ExpectedValues(BaseModel):
    """Values from the COLA application, when supplied.

    Optional throughout (MCH-06): without these the tool still runs every
    compliance check, it simply cannot perform label-versus-application matching.
    """

    brand_name: str | None = None
    class_type: str | None = None
    alcohol_content_pct: float | None = None
    net_contents: str | None = None
    producer_name: str | None = None
    country_of_origin: str | None = None


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


class VerificationResult(BaseModel):
    overall: Status
    checks: list[CheckResult]
    fields: LabelFields
    elapsed_ms: int = Field(description="End-to-end wall time for this label (PRF-03)")
    filename: str | None = None
    usage: dict[str, int] = Field(default_factory=dict, description="Token usage, incl. cache hits")

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is Status.FAIL]

    @property
    def reviews(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is Status.REVIEW]

"""Composition of the rule suite — VAL-14 gating, MCH-06, overall status.

Everything here is a pure function of `LabelFields`. No network, no I/O, no model
call: given the same extraction, the verdict is always the same, and every finding
can be traced to the regulation it came from (D2).
"""

from app.models import (
    ApplicationFields,
    CheckResult,
    LabelFields,
    PairingInfo,
    Status,
    VerificationResult,
)
from app.rules import fields as field_rules
from app.rules import match as match_rules
from app.rules import warning as warning_rules

# Part 16 applies to every alcohol beverage. Parts 4, 5 and 7 differ by commodity,
# and only Part 5 (distilled spirits) is implemented — see requirements §J-4.
TYPE_SPECIFIC_CHECKS = {"VAL-10", "VAL-11", "VAL-12", "VAL-13"}

# VAL-14 reports mandatory fields individually and cites Part 5 for class/type and
# producer, so those rows are type-specific too. Hard-failing a wine label against
# a distilled-spirits citation is the confidently-wrong outcome §J-4 exists to
# prevent, whichever rule ID it arrives under.
PART_5_MANDATORY_FIELDS = {"Class/type designation present", "Producer name and address present"}
FULLY_IMPLEMENTED_TYPES = {"distilled_spirits"}


def _illegible(fields: LabelFields) -> CheckResult:
    """UX-08 — mirror the action an agent already takes on an unreadable image."""
    reason = (fields.illegible_reason or "").strip()
    return CheckResult(
        id="EXT-09",
        name="Label legible",
        status=Status.REVIEW,
        detail=(
            ("This image could not be read reliably" + (f": {reason}." if reason else "."))
            + " Request a clearer photograph of the label before review."
        ),
    )


def _soften_type_specific(check: CheckResult, beverage_type: str) -> CheckResult:
    """Report an unimplemented commodity's rules as unverified, whatever they said.

    Failing a wine label against distilled spirits rules would be confidently
    wrong, which is worse than declining to judge. So would passing it: §J-4
    resolves to flag type-specific fields as *unverified*, and a PASS is an
    assessment, not an abstention.

    The citations are the reason this matters. Wine alcohol content is governed by
    §4.36, not §5.65, and the two differ — a wine below 14% may carry a type
    designation in place of a percentage. Reporting "PASS — 27 CFR 5.65" on a
    Cabernet is a verdict under a regulation that does not govern the product, and
    a tool whose whole claim is that every finding is explainable by citation
    cannot cite the wrong one and call it a pass.
    """
    return check.model_copy(
        update={
            "status": Status.REVIEW,
            "detail": (
                f"Not assessed: this check implements distilled spirits rules (27 CFR Part 5) and "
                f"the label appears to be {beverage_type.replace('_', ' ')}. Review manually."
            ),
        }
    )


def _commodity_mismatch(fields: LabelFields, declared: str) -> CheckResult | None:
    """Flag a label that does not look like the commodity the application declares.

    Field 5 of the COLA application declares the product type. If the label reads
    as something else, one of the two is wrong — most often the extraction, but
    occasionally the application — and either is worth a person's attention.
    """
    if fields.beverage_type == "unknown" or fields.beverage_type == declared:
        return None
    readable = lambda value: value.replace("_", " ")  # noqa: E731
    return CheckResult(
        id="MCH-01",
        name="Product type matches application",
        status=Status.REVIEW,
        expected=readable(declared),
        observed=readable(fields.beverage_type),
        detail=(
            f"The application declares {readable(declared)} but the label reads as "
            f"{readable(fields.beverage_type)}. Confirm which is correct."
        ),
    )


def evaluate(fields: LabelFields, application: ApplicationFields | None = None) -> list[CheckResult]:
    """Run every applicable rule and return the findings."""
    if not fields.image_legible:
        return [_illegible(fields)]

    checks: list[CheckResult] = []
    checks.extend(warning_rules.check_all(fields))  # Part 16 — universal

    # The application's declared type is authoritative where it is supplied;
    # otherwise the commodity can only be inferred from the label.
    declared_type = application.type_of_product if application else None
    effective_type = declared_type or fields.beverage_type

    type_checks = field_rules.check_all(fields, application)
    if declared_type:
        mismatch = _commodity_mismatch(fields, declared_type)
        if mismatch:
            checks.append(mismatch)

    if effective_type not in FULLY_IMPLEMENTED_TYPES:
        type_checks = [
            _soften_type_specific(c, effective_type)
            if c.id in TYPE_SPECIFIC_CHECKS or c.name in PART_5_MANDATORY_FIELDS
            else c
            for c in type_checks
        ]
    checks.extend(type_checks)

    checks.extend(match_rules.check_all(fields, application))  # empty without expected values
    return checks


def overall_status(checks: list[CheckResult]) -> Status:
    """Worst decidable finding wins.

    Advisory checks are excluded. VAL-06..09 depend on millimetre measurement and
    therefore return REVIEW on every label ever submitted; folding them into the
    verdict would make every verdict REVIEW, which tells an agent nothing about
    the label in front of them and abandons the triage the tool exists to provide.
    They remain in `checks` and are surfaced separately as standing caveats.
    """
    decidable = [c for c in checks if not c.advisory]
    if any(c.status is Status.FAIL for c in decidable):
        return Status.FAIL
    if any(c.status is Status.REVIEW for c in decidable):
        return Status.REVIEW
    return Status.PASS


def verify(
    fields: LabelFields,
    application: ApplicationFields | None = None,
    *,
    elapsed_ms: int = 0,
    filename: str | None = None,
    pairing: PairingInfo | None = None,
    usage: dict[str, int] | None = None,
) -> VerificationResult:
    """Full verification for one label."""
    checks = evaluate(fields, application)
    return VerificationResult(
        overall=overall_status(checks),
        checks=checks,
        fields=fields,
        application=application,
        pairing=pairing,
        elapsed_ms=elapsed_ms,
        filename=filename,
        usage=usage or {},
    )

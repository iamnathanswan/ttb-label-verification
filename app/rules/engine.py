"""Composition of the rule suite — VAL-14 gating, MCH-06, overall status.

Everything here is a pure function of `LabelFields`. No network, no I/O, no model
call: given the same extraction, the verdict is always the same, and every finding
can be traced to the regulation it came from (D2).
"""

from app.models import CheckResult, ExpectedValues, LabelFields, Status, VerificationResult
from app.rules import fields as field_rules
from app.rules import match as match_rules
from app.rules import warning as warning_rules

# Part 16 applies to every alcohol beverage. Parts 4, 5 and 7 differ by commodity,
# and only Part 5 (distilled spirits) is implemented — see requirements §J-4.
TYPE_SPECIFIC_CHECKS = {"VAL-10", "VAL-11", "VAL-12", "VAL-13"}
FULLY_IMPLEMENTED_TYPES = {"distilled_spirits"}


def _illegible(fields: LabelFields) -> CheckResult:
    """UX-08 — mirror the action an agent already takes on an unreadable image."""
    reason = (fields.illegible_reason or "").strip()
    return CheckResult(
        id="EXT-09", name="Label legible", status=Status.REVIEW,
        detail=(
            ("This image could not be read reliably" + (f": {reason}." if reason else "."))
            + " Request a clearer photograph of the label before review."
        ),
    )


def _soften_type_specific(check: CheckResult, beverage_type: str) -> CheckResult:
    """Report an unimplemented commodity's rules as unverified rather than failed.

    Failing a wine label against distilled spirits rules would be confidently
    wrong, which is worse than declining to judge.
    """
    if check.status is Status.PASS:
        return check
    return check.model_copy(
        update={
            "status": Status.REVIEW,
            "detail": (
                f"Not assessed: this check implements distilled spirits rules (27 CFR Part 5) and "
                f"the label appears to be {beverage_type.replace('_', ' ')}. Review manually."
            ),
        }
    )


def evaluate(fields: LabelFields, expected: ExpectedValues | None = None) -> list[CheckResult]:
    """Run every applicable rule and return the findings."""
    if not fields.image_legible:
        return [_illegible(fields)]

    checks: list[CheckResult] = []
    checks.extend(warning_rules.check_all(fields))  # Part 16 — universal

    type_checks = field_rules.check_all(fields)
    if fields.beverage_type not in FULLY_IMPLEMENTED_TYPES:
        type_checks = [
            _soften_type_specific(c, fields.beverage_type) if c.id in TYPE_SPECIFIC_CHECKS else c
            for c in type_checks
        ]
    checks.extend(type_checks)

    checks.extend(match_rules.check_all(fields, expected))  # empty without expected values
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
    expected: ExpectedValues | None = None,
    *,
    elapsed_ms: int = 0,
    filename: str | None = None,
    usage: dict[str, int] | None = None,
) -> VerificationResult:
    """Full verification for one label."""
    checks = evaluate(fields, expected)
    return VerificationResult(
        overall=overall_status(checks),
        checks=checks,
        fields=fields,
        elapsed_ms=elapsed_ms,
        filename=filename,
        usage=usage or {},
    )

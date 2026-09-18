"""Mapping a three-valued visual observation onto a check result.

Shared by `warning.py` and `fields.py`. It lives in its own module because both
need it and neither owns it — importing a private helper across rule modules
would couple them for no reason.
"""

from app.models import CheckResult, Observation, Status


def from_observation(
    observation: Observation,
    *,
    id_: str,
    name: str,
    requirement: str,
    citation: str,
    advisory: bool = False,
    negate: bool = False,
) -> CheckResult:
    """Turn a yes/no/unclear reading into PASS, FAIL, or REVIEW.

    `negate=True` inverts the sense, for rules phrased as prohibitions — VAL-04
    requires that the warning body is *not* bold.

    "unclear" always yields REVIEW. Treating it as "no" would reject compliant
    labels on a bad photograph; treating it as "yes" would pass defects silently.
    """
    if observation == "unclear":
        return CheckResult(
            id=id_,
            name=name,
            status=Status.REVIEW,
            citation=citation,
            advisory=advisory,
            detail=f"Could not determine from the image whether {requirement}. Confirm by inspection.",
        )

    satisfied = (observation == "no") if negate else (observation == "yes")
    if satisfied:
        return CheckResult(
            id=id_,
            name=name,
            status=Status.PASS,
            citation=citation,
            advisory=advisory,
            detail=f"Confirmed that {requirement}.",
        )

    return CheckResult(
        id=id_,
        name=name,
        status=Status.REVIEW if advisory else Status.FAIL,
        citation=citation,
        advisory=advisory,
        detail=(
            f"The label appears not to satisfy the requirement that {requirement}."
            + (" A photograph cannot settle this; confirm by inspection." if advisory else "")
        ),
    )

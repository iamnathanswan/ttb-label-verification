"""Match labels to the applications they belong to.

The serial number is the unique identifier of an application — field 4, required —
but it is never printed on the label, because it is not a labelling requirement
under Parts 4, 5, 7 or 16. So two documents cannot be paired by comparing their
contents, and pairing has to work from what surrounds them.

Four strategies, tried in order of how much they can be trusted. Nothing is ever
paired on a guess: a label that cannot be matched confidently is reported
unpaired and still receives the full compliance check, which is the outcome an
agent can act on.
"""

from dataclasses import dataclass, field
from pathlib import PurePath

from app.extract_application import serial_from_filename
from app.models import ApplicationFields, PairingInfo, PairingRule
from app.rules.match import normalise


@dataclass(slots=True)
class Candidate:
    """An application available for pairing."""

    filename: str
    fields: ApplicationFields | None = None


@dataclass(slots=True)
class Pairing:
    label_filename: str
    application: Candidate | None
    info: PairingInfo


@dataclass(slots=True)
class PairingOutcome:
    pairs: list[Pairing] = field(default_factory=list)
    unused_applications: list[Candidate] = field(default_factory=list)


def _stem(filename: str) -> str:
    return PurePath(filename).stem.lower()


def _unpaired(label: str, detail: str) -> Pairing:
    return Pairing(label, None, PairingInfo(rule=PairingRule.UNPAIRED, detail=detail))


def pair(labels: list[str], applications: list[Candidate]) -> PairingOutcome:
    """Match each label to at most one application.

    `labels` and `applications` are filenames; application fields are used only
    where the filename cannot decide.
    """
    outcome = PairingOutcome()

    if not applications:
        for label in labels:
            outcome.pairs.append(
                _unpaired(label, "No application was supplied, so only the regulations were checked.")
            )
        return outcome

    remaining = list(applications)

    # 1. One of each. Unambiguous by construction, and the common case for a
    #    single review, so it is worth not second-guessing with heuristics.
    if len(labels) == 1 and len(applications) == 1:
        application = remaining[0]
        outcome.pairs.append(
            Pairing(
                labels[0], application,
                PairingInfo(
                    rule=PairingRule.SOLE_PAIR,
                    application_filename=application.filename,
                    serial_number=(application.fields.serial_number if application.fields else None) or None,
                    detail="One label and one application were submitted together.",
                ),
            )
        )
        return outcome

    for label in labels:
        match, rule, detail = None, None, ""

        # 2. The application's serial number appears in the label's filename.
        label_serial = serial_from_filename(label)
        if label_serial:
            for candidate in remaining:
                serial = (candidate.fields.serial_number if candidate.fields else "") or ""
                if serial and serial == label_serial:
                    match, rule = candidate, PairingRule.SERIAL_IN_FILENAME
                    detail = f"Serial {serial} appears in both filenames."
                    break

        # 3. Identical filename stems.
        if match is None:
            for candidate in remaining:
                if _stem(label) == _stem(candidate.filename):
                    match, rule = candidate, PairingRule.SHARED_FILENAME_STEM
                    detail = "The files share a name."
                    break

        # 4. Brand name, only where exactly one application could be meant. Two
        #    applications matching one label is not a pair, it is a question.
        if match is None:
            label_stem = normalise(_stem(label))
            brand_matches = [
                candidate for candidate in remaining
                if candidate.fields
                and candidate.fields.brand_name
                and normalise(candidate.fields.brand_name) in label_stem
            ]
            if len(brand_matches) == 1:
                match, rule = brand_matches[0], PairingRule.BRAND_NAME
                detail = (
                    f"The brand “{match.fields.brand_name}” on the application appears in the "
                    "label's filename."
                )
            elif len(brand_matches) > 1:
                outcome.pairs.append(
                    _unpaired(
                        label,
                        f"{len(brand_matches)} applications share this brand, so the correct one "
                        "could not be determined. Name the files with the serial number to pair them.",
                    )
                )
                continue

        if match is None:
            outcome.pairs.append(
                _unpaired(
                    label,
                    "No application matched this label. Only the regulations were checked. "
                    "Name the files with a shared serial number to pair them.",
                )
            )
            continue

        remaining.remove(match)
        outcome.pairs.append(
            Pairing(
                label, match,
                PairingInfo(
                    rule=rule,
                    application_filename=match.filename,
                    serial_number=(match.fields.serial_number if match.fields else None) or None,
                    detail=detail,
                ),
            )
        )

    outcome.unused_applications = remaining
    return outcome

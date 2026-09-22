"""Match labels to the applications they belong to (MCH-10).

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


NO_MATCH = (
    "No application matched this label. Only the regulations were checked. "
    "Name the files with a shared serial number to pair them."
)


@dataclass(slots=True)
class Match:
    """The outcome of searching for one label's application.

    A `candidate` of None means unpaired. `detail` explains why either way, and
    when it is set on a failure it says something more useful than NO_MATCH — an
    ambiguous brand can tell the agent exactly how to resolve it.
    """

    candidate: Candidate | None = None
    rule: PairingRule | None = None
    detail: str = ""


def _find_match(label: str, remaining: list[Candidate]) -> Match:
    """Try each strategy in descending order of trust and stop at the first hit."""

    # 1. The application's serial number appears in the label's filename. COLA
    #    exports are commonly named by serial, so this is the strongest signal
    #    available once there is more than one of each.
    label_serial = serial_from_filename(label)
    if label_serial:
        for candidate in remaining:
            serial = (candidate.fields.serial_number if candidate.fields else "") or ""
            if serial and serial == label_serial:
                return Match(candidate, PairingRule.SERIAL_IN_FILENAME, f"Serial {serial} appears in both filenames.")

    # 2. Identical filename stems — 24-001.pdf against 24-001.png.
    for candidate in remaining:
        if _stem(label) == _stem(candidate.filename):
            return Match(candidate, PairingRule.SHARED_FILENAME_STEM, "The files share a name.")

    # 3. Brand name, and only where exactly one application could be meant. Two
    #    applications sharing a brand is not a pair, it is a question — and the
    #    answer an agent needs is how to make it unambiguous, not a guess.
    label_stem = normalise(_stem(label))
    brand_matches = [
        c for c in remaining if c.fields and c.fields.brand_name and normalise(c.fields.brand_name) in label_stem
    ]
    if len(brand_matches) == 1:
        found = brand_matches[0]
        return Match(
            found,
            PairingRule.BRAND_NAME,
            f"The brand “{found.fields.brand_name}” on the application appears in the label's filename.",
        )
    if len(brand_matches) > 1:
        return Match(
            detail=(
                f"{len(brand_matches)} applications share this brand, so the correct one "
                "could not be determined. Name the files with the serial number to pair them."
            )
        )

    return Match()


def pair(labels: list[str], applications: list[Candidate]) -> PairingOutcome:
    """Match each label to at most one application.

    `labels` and `applications` are filenames; application fields are used only
    where the filename cannot decide.
    """
    outcome = PairingOutcome()

    if not applications:
        for label in labels:
            outcome.pairs.append(_unpaired(label, "No application was supplied, so only the regulations were checked."))
        return outcome

    remaining = list(applications)

    # 1. One of each. Unambiguous by construction, and the common case for a
    #    single review, so it is worth not second-guessing with heuristics.
    if len(labels) == 1 and len(applications) == 1:
        application = remaining[0]
        outcome.pairs.append(
            Pairing(
                labels[0],
                application,
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
        found = _find_match(label, remaining)
        if found.candidate is None:
            outcome.pairs.append(_unpaired(label, found.detail or NO_MATCH))
            continue

        remaining.remove(found.candidate)
        outcome.pairs.append(
            Pairing(
                label,
                found.candidate,
                PairingInfo(
                    rule=found.rule,
                    application_filename=found.candidate.filename,
                    serial_number=(found.candidate.fields.serial_number if found.candidate.fields else None) or None,
                    detail=found.detail,
                ),
            )
        )

    outcome.unused_applications = remaining
    return outcome

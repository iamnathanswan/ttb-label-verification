"""Government health warning checks — VAL-01 through VAL-09.

Normalisation here is deliberately minimal. 27 CFR 16.21 prescribes the statement
word for word, so only whitespace is normalised: case, punctuation, and wording are
compared exactly. `app.rules.match` takes the opposite approach for brand names,
where a casing difference is not a discrepancy. The two policies conflict on
purpose and must not share a helper.
"""

import difflib
import re

from app.models import CheckResult, LabelFields, Status
from app.rules import constants as C
from app.rules.observation import from_observation
from app.rules.units import minimum_type_size_mm, parse_volume_ml


def _collapse_whitespace(text: str) -> str:
    """Fold whitespace runs to single spaces. The only normalisation VAL-01 permits."""
    return re.sub(r"\s+", " ", text).strip()


def describe_first_difference(expected: str, observed: str) -> str:
    """Locate the first divergence and render it with surrounding context.

    Comparison is word-level rather than character-level on purpose. Diffing
    characters finds incidental shared letters and reports fragments like
    'expected "b", found nothing', which tells a reviewer nothing. Whole words
    name the actual edit.
    """
    exp_words, obs_words = expected.split(), observed.split()
    matcher = difflib.SequenceMatcher(None, exp_words, obs_words, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        lead = " ".join(exp_words[max(0, i1 - 5) : i1])
        prefix = "…" if i1 > 5 else ""
        exp_fragment = " ".join(exp_words[i1:i2]) or "nothing"
        obs_fragment = " ".join(obs_words[j1:j2]) or "nothing"
        where = f'after "{prefix}{lead}" ' if lead else "at the start, "
        return f'{where}the required text has "{exp_fragment}" but the label has "{obs_fragment}"'

    return "no difference found"


def check_warning_text(fields: LabelFields) -> CheckResult:
    """VAL-01 — the statement must match 27 CFR 16.21 exactly (whitespace aside)."""
    observed = fields.warning_text or ""
    if not observed.strip():
        return CheckResult(
            id="VAL-01",
            name="Government warning present",
            status=Status.FAIL,
            citation=C.CITE_WARNING_TEXT,
            expected=C.WARNING_STATEMENT,
            observed=None,
            detail="No government health warning was found on this label. It is mandatory on all alcohol beverages.",
        )

    normalised = _collapse_whitespace(observed)
    if normalised == C.WARNING_STATEMENT:
        return CheckResult(
            id="VAL-01",
            name="Government warning text",
            status=Status.PASS,
            citation=C.CITE_WARNING_TEXT,
            detail="The warning matches the required statement word for word.",
        )

    return CheckResult(
        id="VAL-01",
        name="Government warning text",
        status=Status.FAIL,
        citation=C.CITE_WARNING_TEXT,
        expected=C.WARNING_STATEMENT,
        observed=normalised,
        detail=(
            "The warning does not match the required statement exactly — "
            + describe_first_difference(C.WARNING_STATEMENT, normalised)
            + "."
        ),
    )


def check_warning_typography(fields: LabelFields) -> list[CheckResult]:
    """VAL-02, VAL-03, VAL-04 — 27 CFR 16.22(a)(2).

    The final rule is the one most often missed: the regulation bolds the heading
    and forbids bolding the remainder.
    """
    return [
        from_observation(
            fields.warning_heading_is_caps,
            id_="VAL-02",
            name="Warning heading in capitals",
            requirement='"GOVERNMENT WARNING" appears in capital letters',
            citation=C.CITE_WARNING_TYPOGRAPHY,
        ),
        from_observation(
            fields.warning_heading_is_bold,
            id_="VAL-03",
            name="Warning heading in bold",
            requirement='"GOVERNMENT WARNING" appears in bold type',
            citation=C.CITE_WARNING_TYPOGRAPHY,
        ),
        from_observation(
            fields.warning_body_is_bold,
            id_="VAL-04",
            name="Warning body not bold",
            requirement="the text after the heading is not in bold type",
            negate=True,
            citation=C.CITE_WARNING_TYPOGRAPHY,
        ),
    ]


def check_warning_placement(fields: LabelFields) -> list[CheckResult]:
    """VAL-05, VAL-06 — separation (16.21) and contrasting background (16.22(a)(1))."""
    return [
        from_observation(
            fields.warning_visually_separated,
            id_="VAL-05",
            name="Warning set apart",
            requirement="the warning is separate and apart from all other information",
            citation=C.CITE_WARNING_TEXT,
        ),
        from_observation(
            fields.warning_on_contrasting_background,
            id_="VAL-06",
            name="Contrasting background",
            requirement="the warning appears on a contrasting background",
            citation=C.CITE_WARNING_LEGIBILITY,
            advisory=True,
        ),
    ]


def check_warning_measurements(fields: LabelFields) -> list[CheckResult]:
    """VAL-07, VAL-08, VAL-09 — rules a photograph cannot decide.

    Compression, type size, and characters per inch are millimetre measurements.
    An image carries no reliable scale, so these report the applicable threshold
    and route to a human rather than inventing a verdict (D6).
    """
    volume_ml = parse_volume_ml(fields.net_contents_raw)

    compression = CheckResult(
        id="VAL-07",
        name="Warning not compressed",
        status=Status.REVIEW,
        advisory=True,
        citation=C.CITE_WARNING_COMPRESSION,
        detail=(
            "Whether the lettering is compressed below legibility cannot be judged from an image. "
            "Confirm against the physical label."
        ),
    )

    if volume_ml is None:
        unknown = (
            "Net contents could not be read, so the applicable minimum type size cannot be selected. "
            "Determine the container volume, then confirm the warning type size."
        )
        return [
            compression,
            CheckResult(
                id="VAL-08",
                name="Warning type size",
                status=Status.REVIEW,
                advisory=True,
                citation=C.CITE_WARNING_TYPE_SIZE,
                detail=unknown,
            ),
            CheckResult(
                id="VAL-09",
                name="Characters per inch",
                status=Status.REVIEW,
                advisory=True,
                citation=C.CITE_WARNING_CHARS_PER_INCH,
                detail=unknown,
            ),
        ]

    minimum_mm = minimum_type_size_mm(volume_ml)
    max_cpi = C.MAX_CHARS_PER_INCH[minimum_mm]
    volume_text = fields.net_contents_raw or f"{volume_ml:g} mL"

    return [
        compression,
        CheckResult(
            id="VAL-08",
            name="Warning type size",
            status=Status.REVIEW,
            advisory=True,
            citation=C.CITE_WARNING_TYPE_SIZE,
            expected=f"at least {minimum_mm:g} mm",
            detail=(
                f"A container of {volume_text} requires warning text of at least {minimum_mm:g} mm. "
                "Type size cannot be measured from an image; confirm against the physical label."
            ),
        ),
        CheckResult(
            id="VAL-09",
            name="Characters per inch",
            status=Status.REVIEW,
            advisory=True,
            citation=C.CITE_WARNING_CHARS_PER_INCH,
            expected=f"no more than {max_cpi} characters per inch",
            detail=(
                f"At {minimum_mm:g} mm type the warning may carry no more than {max_cpi} characters per inch. "
                "Confirm against the physical label."
            ),
        ),
    ]


def check_all(fields: LabelFields) -> list[CheckResult]:
    """Every warning-related check, VAL-01 through VAL-09."""
    checks = [check_warning_text(fields)]
    checks.extend(check_warning_typography(fields))
    checks.extend(check_warning_placement(fields))
    checks.extend(check_warning_measurements(fields))
    return checks

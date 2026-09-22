# Regulatory sources

Every rule in this tool cites a section of 27 CFR. This page is for checking that
each citation says what the code claims it says, without reading the code.

Text was taken from the Government Publishing Office, 27 CFR 2024 edition, and the
constants live in [`app/rules/constants.py`](../app/rules/constants.py) — a
threshold without its citation is a number nobody can check.

## How to look a rule up

| Source | Use it for | Link |
|---|---|---|
| **eCFR** | Reading a section in a browser. Always current. | `https://www.ecfr.gov/current/title-27/section-16.21` — swap the section number |
| **GPO / govinfo** | The authoritative annual edition, and the machine-readable XML these constants were taken from | [Part 16 XML](https://www.govinfo.gov/content/pkg/CFR-2024-title27-vol1/xml/CFR-2024-title27-vol1-part16.xml) · [Part 5](https://www.govinfo.gov/content/pkg/CFR-2024-title27-vol1/xml/CFR-2024-title27-vol1-part5.xml) · [Part 4](https://www.govinfo.gov/content/pkg/CFR-2024-title27-vol1/xml/CFR-2024-title27-vol1-part4.xml) · [Part 7](https://www.govinfo.gov/content/pkg/CFR-2024-title27-vol1/xml/CFR-2024-title27-vol1-part7.xml) |
| **TTB Beverage Alcohol Manual (BAM)** | Plain-language restatement with examples. Guidance, not the regulation — cite the CFR, not the BAM. | [Distilled spirits](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/beverage-alcohol-manual) · [Malt beverages](https://www.ttb.gov/system/files?file=images%2Fpdfs%2Fbeer-bam%2Fcomplete-malt-beverage-alcohol-manual.pdf) |
| **TTB labeling resources** | Checklists and public guidance | [Labeling resources](https://www.ttb.gov/regulated-commodities/labeling/labeling-resources) |

> The wine BAM is **out of date** — TTB says it has not been updated for the current
> Part 4 rules. Use Part 4 itself.

## Which part applies

Part 16 is universal; the commodity parts are mutually exclusive.

| Commodity | Part | Status here |
|---|---|---|
| Health warning — **all** alcohol beverages | [Part 16](https://www.ecfr.gov/current/title-27/part-16) | Fully implemented |
| Distilled spirits | [Part 5](https://www.ecfr.gov/current/title-27/part-5) | Fully implemented |
| Wine | [Part 4](https://www.ecfr.gov/current/title-27/part-4) | **Not implemented** — see below |
| Malt beverages | [Part 7](https://www.ecfr.gov/current/title-27/part-7) | **Not implemented** — see below |

## Rule-by-rule

Run the tool and every finding shows its citation. This is the same list.

### Health warning — applies to every commodity

| Rule | Citation | What it requires | Verify |
|---|---|---|---|
| VAL-01 | 27 CFR 16.21 | The warning statement, verbatim | [§16.21](https://www.ecfr.gov/current/title-27/section-16.21) |
| VAL-02 | 27 CFR 16.22(a)(2) | `GOVERNMENT WARNING` in capitals | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-03 | 27 CFR 16.22(a)(2) | …and in bold | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-04 | 27 CFR 16.22(a)(2) | The **remainder may not be bold** — only the first two words | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-05 | 27 CFR 16.21 | "separate and apart from all other information" | [§16.21](https://www.ecfr.gov/current/title-27/section-16.21) |
| VAL-06 *(advisory)* | 27 CFR 16.22(a)(1) | Readily legible, contrasting background | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-07 *(advisory)* | 27 CFR 16.22(a)(3) | Not compressed | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-08 *(advisory)* | 27 CFR 16.22(b) | Minimum type size by container volume | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |
| VAL-09 *(advisory)* | 27 CFR 16.22(a)(4) | Maximum characters per inch | [§16.22](https://www.ecfr.gov/current/title-27/section-16.22) |

**Advisory means REVIEW, never FAIL.** A photograph carries no millimetre scale, so
type size and contrast cannot be decided from it. See `docs/requirements.md` D6.

The two thresholds worth checking against the text:

| §16.22(b) — type size | §16.22(a)(4) — characters per inch |
|---|---|
| ≤ 237 mL → 1 mm · > 237 mL to 3 L → 2 mm · > 3 L → 3 mm | 1 mm → 40 · 2 mm → 25 · 3 mm → 12 |

### Distilled spirits — 27 CFR Part 5

| Rule | Citation | What it requires | Verify |
|---|---|---|---|
| VAL-10 | 27 CFR 5.63(a) | Brand name, class/type and alcohol content in the **same field of vision** | [§5.63](https://www.ecfr.gov/current/title-27/section-5.63) |
| VAL-11 | 27 CFR 5.65 | Alcohol content as a percentage by volume | [§5.65](https://www.ecfr.gov/current/title-27/section-5.65) |
| VAL-12 | 27 CFR 5.66(b) | Producer "identified by a phrase describing the function performed" | [§5.66](https://www.ecfr.gov/current/title-27/section-5.66) |
| VAL-13 | 27 CFR 5.69 | Country of origin, for imported product | [§5.69](https://www.ecfr.gov/current/title-27/section-5.69) |
| VAL-14 | 27 CFR 5.64 | Brand name present | [§5.64](https://www.ecfr.gov/current/title-27/section-5.64) |

§5.63(a) defines field of vision as "a single side of a container (for a
cylindrical container, a side is 40 percent of the circumference) where all of the
pieces of information can be viewed simultaneously without the need to turn the
container."

**Proof is not alcohol content.** §5.65 requires percentage by volume. Degrees proof
may appear in addition, never instead — 90 proof with no ABV fails VAL-11.

### Wine and malt beverages — not implemented

A wine or malt beverage label still gets the full Part 16 warning suite, because
Part 16 is universal. The Part 5 rules above are reported as **unverified rather
than failed**, since failing a wine label against a distilled spirits citation is
the confidently-wrong outcome this tool exists to avoid (`requirements.md` §J-4).

The equivalent sections, if the rule set were extended:

| | Wine (Part 4) | Malt beverages (Part 7) |
|---|---|---|
| Mandatory information | §4.32 | §7.63 |
| Brand name | §4.33 | §7.64 |
| Class and type | §4.34 | §7.141–7.143 |
| Alcohol content | §4.36 | §7.65 |
| Name and address | §4.35 | §7.66–7.68 |
| Country of origin | (via §4.35; appellations at §4.25) | §7.69 |

Note the shapes differ — Part 7 splits name and address across three sections by
how the product reached the container, and Part 4 has no single country-of-origin
section. This is why the parts cannot share one rule implementation.

## The application form

TTB F 5100.31, *Application for and Certification/Exemption of Label/Bottle
Approval*, OMB No. 1513-0020 — the form the tool reads. Field numbers used in
`app/extract_application.py` refer to the current revision.

Two things about it that surprise people:

- **It carries no alcohol content and no net contents field.** TTB removed them;
  field 15 asks for container wording only where it does *not* appear on the
  labels. Both are checked against the label's own requirements (VAL-11, VAL-14,
  VAL-08) rather than compared to a form that does not collect them.
- **It runs JavaScript on open** — an alert about LEGAL paper. See
  `docs/security.md` finding 6.

## What is compared, and what is not

§5.65(c) allows "a tolerance of plus or minus 0.3 percentage points… for actual
alcohol content that is above or below the labeled alcohol content." Read it
carefully: it governs *laboratory-measured* content against the *label*. It is not
a tolerance for comparing an application against a label, and the application does
not state an ABV to compare anyway. The tool does not apply it.

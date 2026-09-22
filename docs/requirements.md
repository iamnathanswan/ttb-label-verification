# Requirements — TTB AI Label Verification Prototype

**Status:** v2 — current · **Owner:** Nathan Swan · **Written:** 2026-09-16 · **Last updated:** 2026-09-22

*v2 revises §J-1 and the MCH requirements after the matching layer was rebuilt to extract both documents rather than take application values by hand. The superseded resolution is kept in §J-1 rather than replaced, because why it was wrong is the useful part.*

## How to read this document

Every requirement has a stable ID. Code, tests, and commits reference these IDs so that
coverage is provable rather than asserted. `docs/traceability.md` maps each ID to its
implementation and the test that exercises it.

| Type | Meaning |
|---|---|
| **Binding** | Stated explicitly in the assessment instructions. Non-negotiable. |
| **Derived** | Not in the instructions, but required by 27 CFR. Implementing these is how the tool becomes correct rather than merely plausible. |
| **Assumption** | A gap in the instructions we resolved ourselves. Each is listed in §J with its rationale. |
| **Out of scope** | Deliberately excluded. Listed so exclusion reads as a decision, not an oversight. |

**Sources.** `README.md` of the assessment repo (interview notes with Sarah Chen, Marcus
Williams, Dave Morrison, Jenny Park; Technical Requirements; Deliverables; Evaluation
Criteria); the applicant instruction email dated 2026-09-16; and the Code of Federal
Regulations, Title 27 — Part 16 (health warning statement) and Part 5 (distilled spirits
labeling), 2024 edition, retrieved from GPO.

---

## A. Extraction

| ID | Requirement | Source | Type |
|---|---|---|---|
| EXT-01 | Extract **brand name** from label image | *"Brand name"* — Additional Context | Binding |
| EXT-02 | Extract **class/type designation** | *"Class/type designation"* | Binding |
| EXT-03 | Extract **alcohol content** | *"Alcohol content (with some exceptions for certain wine/beer)"* | Binding |
| EXT-04 | Extract **net contents** | *"Net contents"* | Binding |
| EXT-05 | Extract **name and address of bottler/producer** | *"Name and address of bottler/producer"* | Binding |
| EXT-06 | Extract **country of origin** when present | *"Country of origin for imports"* | Binding |
| EXT-07 | Extract **government warning statement** verbatim, preserving case | *"Government Health Warning Statement (mandatory on all alcohol beverages)"* | Binding |
| EXT-08 | Report a per-field confidence signal, so low-confidence reads route to human review rather than silently passing | — | Assumption |
| EXT-09 | Tolerate imperfect captures: off-angle, poor lighting, glare | Jenny: *"labels that are photographed at weird angles, or the lighting is bad, or there's glare on the bottle"* — flagged by her as *"maybe out of scope"* | Binding (stretch) |
| EXT-10 | Accept common image formats plus PDF | — | Assumption |

## B. Compliance validation (CFR-derived)

These are checks against the regulations themselves, independent of any application record.

| ID | Requirement | Source | Type |
|---|---|---|---|
| VAL-01 | Warning text must match §16.21 **exactly**, word for word, after whitespace normalization | Jenny: *"It has to be **exact**. Like, word-for-word"* / 27 CFR §16.21 | Binding |
| VAL-02 | `GOVERNMENT WARNING` must appear in **capital letters** | Jenny: *"the 'GOVERNMENT WARNING:' part has to be in all caps and bold"*; she caught one using *"'Government Warning' in title case"* / §16.22(a)(2) | Binding |
| VAL-03 | `GOVERNMENT WARNING` must appear in **bold type** | §16.22(a)(2) | Derived |
| VAL-04 | The **remainder of the warning may NOT be bold** | §16.22(a)(2): *"The remainder of the warning statement may not appear in bold type."* Not mentioned in any interview. | Derived |
| VAL-05 | Warning must be **separate and apart from all other information** | §16.21 | Derived |
| VAL-06 | Warning must appear on a **contrasting background** and be legible under ordinary conditions | §16.22(a)(1) | Derived |
| VAL-07 | Warning must not be compressed such that it is not readily legible | §16.22(a)(3) | Derived |
| VAL-08 | Minimum type size is a function of container volume: ≤237 mL → 1 mm; >237 mL to 3 L → 2 mm; >3 L → 3 mm | §16.22(b) | Derived |
| VAL-09 | Max characters per inch by type size: 1 mm → 40; 2 mm → 25; 3 mm → 12 | §16.22(a)(4) | Derived |
| VAL-10 | Brand name, class/type, and alcohol content must appear **within the same field of vision** (one side; for a cylindrical container, 40% of circumference) | §5.63(a) | Derived |
| VAL-11 | Alcohol content must be expressed as **percentage by volume**; proof may additionally be stated but cannot substitute | §5.65(a)–(b) | Derived |
| VAL-12 | Producer name must be preceded by a function phrase — "bottled by", "distilled by", "produced by", "blended by", etc. | §5.66(b) | Derived |
| VAL-13 | Country of origin required for imported products | §5.69 | Derived |
| VAL-14 | Flag missing mandatory fields individually rather than as one aggregate failure | — | Assumption |

**Note on VAL-06 through VAL-09.** These are physical-measurement rules. A photograph
carries no reliable millimeter scale, so these cannot be decided from an image alone.
They are implemented as **advisory** checks that route to human review with the reasoning
shown, never as automated hard failures. This limitation is documented in the README
rather than hidden.

## C. Application matching

| ID | Requirement | Source | Type |
|---|---|---|---|
| MCH-01 | Compare extracted label values against expected application values, field by field | Sarah: *"checks that what's on the label matches what's in the application"* | Binding |
| MCH-02 | Case, punctuation, and whitespace differences must not produce a hard failure | Dave: *"'STONE'S THROW' on the label but 'Stone's Throw' in the application... it's obviously the same thing. You need judgment."* | Binding |
| MCH-03 | ABV and net contents are **not** compared against the application — neither is a field on TTB F 5100.31 | §5.65(c) governs laboratory-measured content against the label, not application against label | Derived |
| MCH-04 | Results are three-state — `PASS` / `REVIEW` / `FAIL` — never a bare boolean | Dave: *"there's nuance. You can't just pattern match everything."* | Assumption |
| MCH-05 | Every `REVIEW` and `FAIL` shows both values side by side plus a plain-language reason | Dave: *"Just don't make my life harder in the process."* | Assumption |
| MCH-06 | An application is **optional**; with none supplied the tool still runs §B compliance checks | Resolves the ambiguity in §J-1 | Assumption |
| MCH-07 | Application values are **extracted, never typed** | Sarah: *"half their day doing what's essentially data entry verification"* | Binding |
| MCH-08 | Read the application from its form fields where possible; fall back to vision for scanned forms | TTB F 5100.31 is an AcroForm; exact beats inferred | Assumption |
| MCH-09 | Report how the application was read, so an agent can weigh the value | — | Assumption |
| MCH-10 | Pair labels to applications without guessing; report anything unmatched with how to fix it | The serial number is not printed on labels, so pairing cannot be settled by content | Assumption |
| MCH-11 | Show the source documents beside the findings | A verification tool has to be checkable | Assumption |

## D. Performance

| ID | Requirement | Source | Type |
|---|---|---|---|
| PRF-01 | Single label returns results in **≈5 seconds** | Sarah: *"**If we can't get results back in about 5 seconds, nobody's going to use it.**"* | Binding |
| PRF-02 | Batch streams results as each label completes; first result visible within the PRF-01 budget | Derived from PRF-01 + BAT-01 — see §J-3 | Assumption |
| PRF-03 | Measured elapsed time displayed per label | Sarah's team abandoned the prior vendor over latency; the claim should be visible, not asserted | Assumption |
| PRF-04 | Images downscaled before model submission to reduce latency | — | Assumption |

## E. User experience and accessibility

| ID | Requirement | Source | Type |
|---|---|---|---|
| UX-01 | Usable by a non-technical 73-year-old | Sarah: *"something **my mother could figure out**—she's 73"* | Binding |
| UX-02 | Serve both low- and high-tech-comfort users | Sarah: *"Dave's been here since the Clinton administration and still prints his emails. Meanwhile, Jenny's fresh out of college"* | Binding |
| UX-03 | Clean, obvious controls; no hunting for buttons | Sarah: *"Clean, obvious, no hunting for buttons."* | Binding |
| UX-04 | Status conveyed by icon **and** text, never colour alone | Section 508 / WCAG 2.1 AA — legally required for federal software | Derived |
| UX-05 | Full keyboard navigation and screen-reader labelling | Section 508 | Derived |
| UX-06 | Minimum AA contrast; large targets and type | Section 508; *"Half our team is over 50"* | Derived |
| UX-07 | Errors state what happened and what to do next | Evaluation criterion: *"User experience and error handling"* | Binding |
| UX-08 | Unreadable image produces an actionable "request better image" outcome, matching existing practice | Jenny: *"if an agent can't read the label they just reject it and ask for a better image"* | Assumption |

## F. Batch processing

| ID | Requirement | Source | Type |
|---|---|---|---|
| BAT-01 | Accept multiple label uploads at once | Sarah: *"**handle batch uploads**"* | Binding |
| BAT-02 | Target 200–300 labels per batch | Sarah: *"big importers who dump 200, 300 label applications on us at once"* | Binding |
| BAT-03 | Per-label progress and a batch summary | Implied by BAT-02 | Assumption |
| BAT-04 | One failure must not abort the batch | — | Assumption |
| BAT-05 | Export batch results to CSV | Janet, Seattle office — *"has been asking about this for years"* | Assumption |
| BAT-06 | Bounded concurrency to protect latency and rate limits | Derived from PRF-02 | Assumption |

## G. Operations, security, deployment

| ID | Requirement | Source | Type |
|---|---|---|---|
| OPS-01 | Stateless — no uploaded label or extracted content persisted | Marcus: *"We're not storing anything sensitive for this exercise."* | Binding |
| OPS-02 | Model provider behind a swappable interface | Marcus: *"our network blocks outbound traffic to a lot of domains... half their features didn't work because our firewall blocked connections to their ML endpoints"* | Assumption |
| OPS-03 | Document an Azure-hosted inference path for production | Marcus: *"We're on Azure now after the migration in 2019."* | Assumption |
| OPS-04 | No secrets in client code or repository | Standard practice; federal deliverable | Derived |
| OPS-05 | Rate limiting and upload size caps on the public URL | Public endpoint with a funded API key behind it | Assumption |
| OPS-06 | Standalone — no COLA integration | Marcus: *"we're not looking to integrate with COLA directly"* | Binding |
| OPS-07 | Uploaded documents are stripped of executable content before display | A PDF can carry JavaScript that every mainstream viewer runs on open; TTB F 5100.31 itself does | Derived |

## H. Deliverables

| ID | Requirement | Source | Type |
|---|---|---|---|
| DEL-01 | Public source repository with all source code | Deliverables §1 | Binding |
| DEL-02 | README with setup and run instructions | Deliverables §1 | Binding |
| DEL-03 | Documentation of approach, tools used, assumptions made | Deliverables §1 | Binding |
| DEL-04 | Deployed, working application URL | Deliverables §2 | Binding |
| DEL-05 | Trade-offs and limitations documented | *"Document any trade-offs or limitations."* | Binding |
| DEL-06 | Submitted via the Microsoft Forms link within one week of 2026-09-16 | Instruction email | Binding |

## I. Explicitly out of scope

| ID | Excluded | Rationale |
|---|---|---|
| OOS-01 | COLA system integration | Marcus: *"that's a whole different beast with its own authorization requirements"* |
| OOS-02 | Authentication / user accounts | No requirement stated; OPS-01 removes the need |
| OOS-03 | Database or persistence layer | OPS-01 |
| OOS-04 | FedRAMP / ATO artifacts | Marcus: *"for a prototype? Just don't do anything crazy"* |
| OOS-05 | Formula approval, ingredient, or allergen review | Not in scope of label verification as described |
| OOS-06 | Full wine (Part 4) and malt beverage (Part 7) rule sets | Sample is distilled spirits; Parts 4 and 7 differ. Prototype targets Part 5 with graceful handling of other types — see §J-4 |

## J. Ambiguities identified and how we resolved them

**J-1 — Is this label-only verification, or label-versus-application matching?**
The explicit requirements list label fields only. The interviews describe something
else: Sarah says the review *is* matching — *"making sure the number on the form is the
same as the number on the label. My agents spend half their day doing what's essentially
data entry verification"* — and Dave's "STONE'S THROW" against "Stone's Throw" is
explicitly label-versus-application.

*First resolution, and why it was wrong.* This was originally resolved as "build both,
with matching optional", taking application values by hand or by CSV. That satisfied the
letter of both readings and defeated the point of one: a tool that asks an agent to type
the application values is asking for exactly the work Sarah describes them drowning in.
The CSV was worse — the application is a filled PDF form, so the input format was designed
for an artifact that does not exist.

*Resolution.* Both documents are uploaded and both are extracted. The label is read by a
vision model; the application is read from the AcroForm fields of TTB F 5100.31, exactly
and without a model, falling back to vision only where a form was printed and scanned.
Nothing is retyped. Compliance still runs on a label submitted alone, so the narrower
reading is fully served as well.

**J-2 — Does "5 seconds" mean per label or per batch?**
300 labels in 5 seconds is not achievable; 300 × 5 s sequentially is 25 minutes, which
fails the intent. The figure is quoted against a prior vendor taking "30, 40 seconds...
to process a single label," so it is a per-label benchmark. *Resolution:* ≈5 s per label,
with batch results streaming as they complete so an agent begins work within the same
budget.

**J-3 — What is the source of truth for the warning text?**
The instructions say only "[Standard government warning text]". *Resolution:* 27 CFR
§16.21, retrieved from GPO, embedded as a versioned constant with the citation in-line.

**J-4 — Which beverage types must be supported?**
Requirements differ across beer, wine, and spirits, and the instructions note "some
exceptions for certain wine/beer" without specifying. *Resolution:* implement Part 5
(distilled spirits) rules fully, since the sample is a bourbon; detect type and, for wine
and malt beverages, apply only the universally applicable checks (§16 warning) while
flagging type-specific fields as unverified rather than failing them.

**J-5 — Is an external model API acceptable given the firewall constraint?**
Marcus reports that outbound traffic is blocked to many domains, and that the scanning
vendor's ML endpoints were unreachable as a result.

*Why it does not bind the prototype.* That firewall governs traffic leaving TTB's network.
This prototype is deployed outside it, so an agent's browser makes exactly one outbound
connection — to the application URL. The call to the inference API is made by the
application host, never from a TTB workstation. The scanning vendor failed because its
product called ML endpoints from inside the network; this one does not.

*Why it still matters.* A production deployment would run inside TTB's environment, and
there the inference endpoint is exactly the kind of domain that gets blocked. The remedy
is not a firewall exception but moving inference inside the trust boundary — TTB migrated
to Azure in 2019, so Azure-hosted inference is the natural path. This is the reason for
the provider seam (OPS-02): switching is a constructor change, not a rewrite. The path is
documented under OPS-03.

*The residual risk, which is ours.* If TTB's firewall blocks the deployment host itself, a
reviewer cannot reach the application at all. Nothing in the design prevents that, so the
repository is made to stand alone: `docs/verification.md` records real results from the
deployed service, and the README carries screenshots and local run instructions.

## K. Traceability

Maintained in `docs/traceability.md`: one row per ID above, with implementing module,
covering test, and status. A requirement without a test is treated as not done.

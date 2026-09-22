# CLAUDE.md

Working agreement for this repository. It records the constraints, the one architectural
invariant, and the mistakes that are easy to make in this problem domain, so that each
session starts from the same footing rather than rediscovering them.

**Project.** AI-assisted verification of alcohol beverage labels against TTB requirements.
Take-home assessment for IT Specialist (AI), Treasury Common Services Center.

---

## Orientation

| Document | What it holds |
|---|---|
| `docs/requirements.md` | 58 requirements with stable IDs. The source of truth. |
| `docs/plan.md` | Architecture, data contracts, decisions D1–D8, risks. |
| `docs/tasks.md` | Seven phases, 45 tasks, each carrying its REQ IDs. |
| `docs/traceability.md` | Coverage matrix. Generated — never edit by hand. |
| `docs/security.md` | Security review findings and what was accepted. |
| `docs/perf.md` | Measured latency against PRF-01, and what was tried. |
| `docs/verification.md` | Corpus results. Generated — never edit by hand. |

`python3 docs/check_coverage.py` cross-checks requirement IDs across the spec documents and
must exit 0. Run it after editing any of them.

## The invariant (D2)

**The model extracts. Code judges.**

Exactly one call in this system is non-deterministic, and it returns a validated
`LabelFields` object. Every compliance determination is a pure function over that object —
no network, no I/O, no second model call.

This is not stylistic. A compliance decision has to be reproducible, auditable, and
explainable by citation, and a regulator's question is "which rule, and what does it say"
rather than "what did the model think". It also means the rule suite runs in milliseconds
with no API key.

Do not ask the model for a verdict, a score, or a pass/fail. If a rule seems hard to
express in code, that is a signal to reread the CFR, not to delegate the judgment.

## Why three states, not two

Results are `PASS`, `REVIEW`, or `FAIL` — never a boolean. The tool exists to clear routine
matching off a 47-person team's desk, not to make final determinations. Two failure modes
matter and they pull in opposite directions:

- Silently passing something a human would have caught defeats the purpose of review.
- Hard-failing something obviously fine ("STONE'S THROW" against "Stone's Throw") makes the
  tool worse than the eyeball it replaced, and it will be abandoned. A previous vendor
  pilot was abandoned within weeks.

`REVIEW` is therefore the honest answer whenever the rule is satisfied in substance but not
in form, or whenever the evidence available from a photograph is insufficient to decide.
Every `REVIEW` and `FAIL` shows the expected value, the observed value, and the citation.

## Hard constraints

Changing any of these means changing `docs/requirements.md` first.

| Constraint | ID | Note |
|---|---|---|
| ≈5 s per label | `PRF-01` | Binding. Measure; never assume. Batch streams — the first result lands inside the budget. |
| Three states | `MCH-04` | See above. |
| Stateless | `OPS-01` | Nothing reaches disk or a database. Uploads live in memory for the request. |
| Section 508 / WCAG 2.1 AA | `UX-04..06` | Status by icon **and** word, never colour alone. Fully keyboard operable. |
| No secrets in the client or the repo | `OPS-04` | Server-side environment variable only. |
| Physical measurements are advisory | `VAL-06..09`, D6 | A photograph carries no millimetre scale. These return `REVIEW`, never `FAIL`. |

## Domain pitfalls

These have a real cost and are easy to get backwards.

**Normalisation policy is deliberately opposite in two adjacent modules.**
`rules/warning.py` (`VAL-01`) compares the warning against §16.21 after whitespace
normalisation *only* — no case folding, no punctuation stripping. The regulation demands
exactness, and "Government Warning" in title case is a genuine rejection. Meanwhile
`rules/match.py` (`MCH-02`) *does* fold case, punctuation, whitespace, and diacritics,
because a brand-name casing difference is not a discrepancy. Do not share a normalisation
helper between them; the requirements conflict on purpose.

**Proof is not alcohol content.** §5.65 requires a statement as percentage by volume;
degrees proof may appear *in addition* but never instead. 90 proof present with no ABV is a
failure of `VAL-11`, not a 45% match.

**Net contents feeds the warning rules.** The §16.22(b) minimum type size depends on
container volume, so `net_contents_ml` must be parsed to a number and unit-normalised
(fl oz → mL) before `VAL-08` can select a threshold. A label whose net contents failed to
extract cannot have its type size evaluated — return `REVIEW`, not a guess.

**The ABV tolerance is for comparison only.** §5.65(c) allows ±0.3 percentage points
between stated and actual content, which governs `MCH-03` when matching a label against an
application. It is not licence to round, reformat, or accept a missing ABV statement.

**Both sides are extracted; nothing is typed.** The application is a filled
TTB F 5100.31 and is read from its AcroForm widgets — exactly, with no model — falling
back to vision only for a form that was printed and scanned. Asking an agent to type
application values reintroduces the data entry the tool exists to remove (§J-1).

**A PDF is executable, and the TTB form proves it.** TTB F 5100.31 carries a
document-level script that fires `app.alert("Please set page size to LEGAL...")` on
open, and every mainstream PDF viewer runs it. Anything handed to a browser viewer
goes through `app/sanitize.py` first (`OPS-07`). Note that the script lives in a
compressed stream: searching the raw bytes for `app.alert` returns False even for
the untouched original, so assert against decompressed objects or the test proves
nothing.

**The serial number cannot pair by content.** It identifies an application (field 4) but
is never printed on a label, so pairing works from filenames and, failing that, an
unambiguous brand. Two candidates is a question, not a pair — `app/pairing.py` reports
rather than guesses.

**Source and type are radio groups read by export state**, not by position. Both source
widgets sit at the same y coordinate, printed side by side, so sorting by position picks
between Domestic and Imported arbitrarily. States are `Domes`/`Import` and
`Wine`/`Spirits`/`Malt`.

**Application values follow the form, not the interviews.** `ExpectedValues` mirrors
TTB F 5100.31. There is no class/type field on it and no country-of-origin field; field 3
declares Domestic or Imported and field 5 declares the commodity. Those two are
declarations that decide *which rules apply* — they drive `VAL-13` and the commodity
gating rather than being compared field to field.

**Beverage type gates which rules apply.** Parts 4 (wine) and 7 (malt beverages) differ
from Part 5 (distilled spirits). For non-spirits, run the Part 16 warning checks — which
are universal — and mark type-specific fields unverified rather than failing them
(`docs/requirements.md` §J-4).

## Regulatory sources

Retrieved from GPO; constants live in `app/rules/constants.py` with citations inline.

| Citation | Governs |
|---|---|
| 27 CFR §16.21 | Warning text, verbatim; "separate and apart from all other information" |
| 27 CFR §16.22(a)(2) | `GOVERNMENT WARNING` in caps and bold; **remainder may not be bold** |
| 27 CFR §16.22(a)(4), (b) | Characters per inch; minimum type size by container volume |
| 27 CFR §5.63(a) | Brand name, class/type, and ABV within the same field of vision |
| 27 CFR §5.65 | ABV as percentage by volume; ±0.3 point tolerance |
| 27 CFR §5.66(b) | Producer name preceded by a function phrase ("bottled by", "distilled by", …) |

## Stack

Python 3.11+ · FastAPI + uvicorn · Pydantic · `anthropic` · Pillow · pytest · ruff
React + Vite, built and served by FastAPI as static files — one service, one URL (D1)
Docker → Railway

## Model configuration

`claude-sonnet-5`, overridable via `ANTHROPIC_MODEL`. Chosen on measured latency against a
binding requirement, not cost: Opus 5 missed the budget at 5,590 ms, Sonnet 5 meets it at
p50 4,185 ms / p95 4,242 ms with identical accuracy on the discriminating typographic
fixtures (`docs/perf.md`).

- **Constrained decoding is not used.** `messages.parse()` against `LabelFields` exceeded
  120 s per label. The schema is supplied to the model as documentation inside the cached
  system prompt, and the response is validated with `LabelFields.model_validate_json()`.
  Shape is still guaranteed; only the decoding constraint is gone.
- `output_config={"effort": "low"}` — extraction is perception, not reasoning.
- `max_tokens` ≈ 2000 — the output is one small JSON object.
- `cache_control={"type": "ephemeral"}` on the system prompt, which is byte-identical across
  every label in a batch. Verify with `usage.cache_read_input_tokens`.
- The system prompt must **never** contain the §16.21 warning text. Showing the model the
  canonical wording invites it to report the canonical wording, silently repairing the exact
  defects `VAL-01` exists to catch. The model transcribes; code compares.
- `budget_tokens` is **removed** on Opus 5 and returns 400. Assistant prefill is also removed.
- Latency is dominated by output generation, not input size or reasoning depth. Shrinking the
  image or disabling thinking measurably did **not** help; both were tried. Fast mode returns
  429 on this workspace, so it is not an available lever.

The SDK is called only from `app/providers/`. `ExtractionProvider` is the seam (`OPS-02`),
and `StubProvider` is what the test suite runs against.

## Conventions

- Every rule function names its REQ ID and CFR citation in its docstring.
- Regulatory constants live in `app/rules/constants.py`. Never inline a threshold or the
  warning text at a call site.
- Tests are named for the requirement: `test_val_04_warning_body_not_bold`.
- Rule tests never touch the network.
- Commit messages reference REQ IDs where applicable.
- Prefer the boring implementation. This is a prototype judged on code quality; cleverness
  that needs explaining is a liability.

## Commands

```bash
./scripts/check.sh                       # everything CI runs — use before every commit
uvicorn app.main:app --reload            # API + UI
cd web && npm run dev                    # frontend only, hot reload
pytest -q                                # rules + API, no network
python3 docs/check_coverage.py           # spec cross-reference; must exit 0
python scripts/benchmark.py 12           # PRF-01 latency; rewrites docs/perf.md figures
python scripts/verify_corpus.py \
  --url $DEPLOYED --markdown docs/verification.md   # regenerate the evidence
python scripts/gen_traceability.py       # rebuild the coverage matrix
python scripts/gen_traceability.py --check   # fail if a requirement has no test
cd web && npm test                       # frontend tests
docker build -t ttb . && docker run -p 8000:8000 --env-file .env ttb
railway up                               # deploy
```

## Non-goals

COLA integration · authentication · persistence · FedRAMP artifacts · formula and ingredient
review · complete Part 4 and Part 7 rule sets.

These are excluded deliberately (`docs/requirements.md` §I). If a task appears to require
one, that is a misreading of the specification — check §I before building anything.

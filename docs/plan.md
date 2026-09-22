# Technical Plan — TTB AI Label Verification Prototype

**Status:** draft v1 · **Owner:** Nathan Swan · **Date:** 2026-09-16 · **Due:** 2026-09-23

Companion documents: `docs/requirements.md` (58 requirements, IDs referenced throughout),
`docs/tasks.md` (execution breakdown), `docs/traceability.md` (coverage matrix).

---

## 1. Shape of the system

A single deployed service. FastAPI owns the HTTP surface and serves the compiled React
bundle as static files, so the deliverable is one URL (`DEL-04`) with one deploy and no
CORS surface.

```
 Browser (React/Vite)
     │  multipart upload  ── client-side downscale ──▶  POST /api/verify        (single)
     │                                                  POST /api/verify/batch  (SSE)
     ▼
 FastAPI
     ├─ ingest.py     decode · normalise · downscale (PRF-04)
     ├─ providers/    ExtractionProvider (ABC) ── AnthropicProvider   (OPS-02)
     │                       │
     │                       ▼  the only non-deterministic boundary
     │                 LabelFields  (pydantic)
     ├─ rules/        pure functions over LabelFields — no I/O, no network
     │                  warning.py   VAL-01..09
     │                  fields.py    VAL-10..14
     │                  match.py     MCH-01..06
     ▼
 VerificationResult   PASS | REVIEW | FAIL  + per-check reasons + timings
```

**The load-bearing decision:** the model extracts, it does not judge. Every compliance
determination is a pure Python function over a validated Pydantic object. Consequences:
the rule suite is unit-testable with zero network calls, each rule sits next to the CFR
citation it implements, and non-determinism is confined to one function that can be
stubbed in tests.

## 2. Repository layout

```
ttb-label-verification/
├── README.md                    setup, approach, assumptions, trade-offs (DEL-02, DEL-03, DEL-05)
├── Dockerfile                   single reproducible build
├── pyproject.toml
├── docs/
│   ├── requirements.md  plan.md  tasks.md  traceability.md
├── app/
│   ├── main.py                  FastAPI app, static mount, routes
│   ├── api.py                   HTTP surface: verify, batch, preview, document
│   ├── config.py                settings, limits, concurrency ceiling
│   ├── limits.py                per-client rate limiting
│   ├── ingest.py                decode, EXIF-normalise, downscale, pixel ceiling
│   ├── sanitize.py              strip executable content from a PDF before display
│   ├── models.py                LabelFields, ApplicationFields, CheckResult, VerificationResult
│   ├── extract_application.py   read TTB F 5100.31 from its AcroForm widgets
│   ├── pairing.py               match labels to applications, or report that it cannot
│   ├── providers/
│   │   ├── base.py              ExtractionProvider ABC, StubProvider
│   │   └── anthropic_provider.py
│   ├── rules/
│   │   ├── constants.py         §16.21 warning text, type-size table, tolerances
│   │   ├── units.py             volume parsing and normalisation to mL
│   │   ├── observation.py       the yes/no/unclear three-state helper
│   │   ├── warning.py  fields.py  match.py  engine.py
│   └── batch.py                 bounded-concurrency fan-out, SSE event stream
├── web/src/
│   ├── App.jsx                  one screen: upload state and workspace state
│   ├── components/              UploadBar · DropZone · DropOverlay · DocumentPane
│   │                            Lightbox · Comparison · ResultCard
│   └── lib/                     sse · csv · downscale · preview · useFileDrop
└── tests/
    ├── test_rules_*.py          pure, no network
    ├── test_api.py              stubbed provider
    ├── test_load.py             300-label fan-out against the stub
    └── fixtures/                label corpus and application corpus, each with expected.json
```

*Modules after `ingest.py` — `sanitize`, `extract_application`, `pairing` — arrived with
Phase 7 and `OPS-07`; this tree is kept current rather than as a record of the first
sketch. `docs/tasks.md` holds the record.*

## 3. Data contracts

`LabelFields` is the extraction schema and the boundary contract. It is also the Pydantic
model handed to the API as the structured-output format, so the schema is declared once.

```python
class LabelFields(BaseModel):
    brand_name: str = ""                  # EXT-01, VAL-14
    class_type: str = ""                  # EXT-02, VAL-14
    alcohol_content_pct: float | None     # VAL-11 — percent by volume
    alcohol_content_proof: float | None   # optional in addition, never instead
    net_contents_raw: str = ""            # parsed to mL by rules/units.py for VAL-08
    producer_name: str = ""
    producer_address: str = ""
    producer_function_phrase: str = ""    # VAL-12 — "bottled by", "distilled by", ...
    country_of_origin: str = ""
    warning_text: str = ""                # verbatim, case preserved (EXT-07)
    warning_heading_is_caps: Observation  # VAL-02
    warning_heading_is_bold: Observation  # VAL-03
    warning_body_is_bold: Observation     # VAL-04
    warning_visually_separated: Observation          # VAL-05
    warning_on_contrasting_background: Observation   # VAL-06
    same_field_of_vision: Observation                # VAL-10
    beverage_type: BeverageType = "unknown"
    image_legible: bool = True
    illegible_reason: str = ""
    low_confidence_fields: list[str] = []  # EXT-08
```

Two shapes here are deliberate and were arrived at by measurement, not preference.

**Absent text is `""`, not `None`.** Every nullable field is a union, and the schema the
model is given has a complexity budget; seventeen of them exceeded it. An empty string
carries the same meaning — *not printed on this label* — at a fraction of the cost. Rules
test falsiness, so the distinction never reaches the regulatory logic.

**Typographic judgements are `Observation`, not `bool | None`.** `Observation` is
`Literal["yes", "no", "unclear"]`. A boolean forces the model to guess on a photograph
where the answer genuinely cannot be seen, and a guess dressed as a certainty is the one
output this tool must not produce. `unclear` routes to a person instead (`rules/observation.py`).

`ApplicationFields` mirrors TTB F 5100.31 and carries `extraction_source`
(`form_fields` or `vision`) so an agent knows whether a value was read exactly or inferred.

`CheckResult` carries `id` (the REQ ID), `status`, `detail`, `expected`, `observed`,
`citation`, `advisory`, and a `category` derived from the ID so it cannot drift from the
rule. `VerificationResult` aggregates checks plus `overall`, `elapsed_ms` (`PRF-03`),
`pairing`, and `provider_usage`.

## 4. Extraction

**Model:** `claude-sonnet-5` via the `anthropic` Python SDK, overridable with
`ANTHROPIC_MODEL`.

*This plan originally specified `claude-opus-5`.* Opus missed the binding latency
requirement at 5,590 ms; Sonnet 5 meets it at p50 4,185 ms with identical accuracy on the
fixtures that discriminate — the typographic ones, where a wrong answer is a wrong verdict.
`PRF-01` decided it, not cost. The measurements are in `docs/perf.md`.

**Call shape:** one `client.messages.create(...)` with the image as a base64 `image`
content block, validated on return with `LabelFields.model_validate_json()`.

*This plan originally specified `client.messages.parse()` with `output_format=LabelFields`.*
Constrained decoding against this schema exceeded **120 seconds per label** against a 5
second budget. The schema is now supplied to the model as documentation inside the cached
system prompt and the response is validated on the way back: the shape is still guaranteed
by Pydantic, only the decoding constraint is gone.

**Latency configuration.** `PRF-01` is binding, so the defaults are wrong for this call:

| Setting | Value | Why |
|---|---|---|
| `output_config={"effort": "low"}` | low | Extraction is perception, not reasoning. |
| `max_tokens` | ~2000 | Output is one small JSON object. |
| `cache_control={"type": "ephemeral"}` | on | System prompt carries extraction instructions and the target schema — byte-identical across every label in a batch. It deliberately excludes the §16.21 text; see below. Verify with `usage.cache_read_input_tokens`. |
| image longest edge | ≤1600 px | Label text stays legible; input tokens and upload time drop sharply (`PRF-04`). |

`budget_tokens` is removed on the Claude 5 models and returns a 400 — not used. Assistant
prefill is likewise removed; structure comes from validation, not from a primed turn.

Latency is dominated by output generation rather than input size or reasoning depth.
Shrinking the image and disabling thinking were both measured and neither helped; the full
table of what was tried is in `docs/perf.md`. Fast mode was considered as an escape hatch
and is unavailable on this workspace (429), which also suits `OPS-03`: it is Claude API
only, so depending on it would have traded against the Azure path.

**Provider abstraction (`OPS-02`).** `ExtractionProvider.extract(image_bytes, media_type)
-> LabelFields` is the whole interface. `AnthropicProvider` implements it; `StubProvider`
backs the test suite. Marcus's firewall story and the Azure production path are documented
against this seam.

## 5. Validation

Rules are pure, individually addressable, and carry their citation inline.

**Warning statement.** `VAL-01` compares against the §16.21 constant after whitespace
normalisation only — no case folding, no punctuation stripping, since the requirement is
exactness. A character-level diff is returned on mismatch so the agent sees *what*
differs. `VAL-02`/`VAL-03` check the heading is caps and bold; `VAL-04` checks the
remainder is **not** bold, which no interview mentions and which most implementations will
miss.

**Physical-measurement rules.** `VAL-06` through `VAL-09` (contrasting background,
compression, type size by volume, characters per inch) depend on millimetre measurement. A
photograph carries no reliable scale. These return `REVIEW` with the reasoning and the
applicable threshold shown — never an automated `FAIL`. Stated plainly in the README
rather than quietly fudged.

**Matching.** `MCH-02` normalises case, punctuation, whitespace, and diacritics before
comparison; an exact match is `PASS`, a normalisation-only difference is `REVIEW` with both
values shown, anything else is `FAIL`. `MCH-03` records that ABV and net contents are
*not* compared: neither is a field on TTB F 5100.31, and §5.65(c)'s ±0.3 percentage-point
tolerance governs laboratory-measured content against the label rather than the application
against the label. Three states throughout (`MCH-04`); never a bare boolean.

## 6. Batch and streaming

`POST /api/verify/batch` accepts N files and returns an SSE stream. An
`asyncio.Semaphore` bounds in-flight requests (`BAT-06`); each completion emits a
`result` event, so the first card renders within the `PRF-01` budget while the remainder
fill in (`PRF-02`). A failed label emits an `error` event and the batch continues
(`BAT-04`). Client uses `AsyncAnthropic` with the aiohttp backend for the fan-out.

Interpretation of "5 seconds" is per label, not per batch — reasoning recorded in
`requirements.md` §J-2.

## 7. Interface

One screen with two states. Nothing uploaded: two drop zones, labels and applications.
Anything uploaded: the zones collapse to a compact bar and the room goes to the work — the
source documents on the left, the findings on the right, split into compliance and
matching. No settings, no navigation (`UX-01`, `UX-03`).

Files can be dropped anywhere on the page at any time, because a drop that misses a target
by a few pixels would otherwise hit the browser default, open the file, and destroy the
queue. An overlay says so for the duration of a drag rather than spending permanent space
on it.

A queue longer than eight collapses to its counts. At the 300 Sarah describes, one chip per
file grew the bar past the height of the viewport and pushed the button that starts the job
off screen.

Section 508 / WCAG 2.1 AA is a legal requirement for federal software, and it happens to
be the same thing Sarah asked for. Status is conveyed by icon **and** word — `PASS`,
`REVIEW`, `FAIL` — never colour alone (`UX-04`); full keyboard operation and labelled
live regions for streaming results (`UX-05`); AA contrast, large targets, 16 px minimum
type (`UX-06`). Every error says what happened and what to do next (`UX-07`), and an
illegible image produces "request a better image" — the action agents already take today
(`UX-08`).

## 8. Deployment

Docker image on Railway: multi-stage build (Vite build → Python runtime), single service,
HTTPS URL. *(This plan originally said Render; Railway was chosen because the account
already existed and was funded.)* API key injected as an environment variable, never in client code or repo
(`OPS-04`). Per-IP rate limit, request size cap, and per-batch file ceiling protect a
publicly reachable endpoint with a funded key behind it (`OPS-05`). Nothing is written to
disk or database — uploads live in memory for the duration of the request (`OPS-01`).

## 9. Decisions and rationale

| # | Decision | Rationale | Rejected alternative |
|---|---|---|---|
| D1 | Single service | One URL per `DEL-04`; no CORS; one deploy to fail | Split React/Vercel + API/Render |
| D2 | Model extracts, code judges | Testable, auditable, citable rules; determinism where it matters | Ask the model for a compliance verdict |
| D3 | Pydantic as the single schema | One declaration serves extraction, validation, and API response | Hand-written JSON schema plus separate types |
| D4 | Three-state results | Dave: *"there's nuance. You can't just pattern match everything."* | Boolean pass/fail |
| ~~D5~~ | ~~Optional expected values~~ — **superseded by D9** | Resolved §J-1 without betting on one reading, and in doing so asked agents to type the values the tool exists to stop them typing | Pick one interpretation |
| D9 | Both documents are extracted; nothing is typed | Sarah describes agents drowning in *"data entry verification"*. A tool that asks for the application values by hand adds to that work instead of removing it (§J-1) | Type them, or upload a CSV of them |
| D6 | Advisory-only physical checks | A JPEG has no millimetre scale; claiming otherwise fails under questioning | Assert type-size compliance |
| D7 | Stateless | Marcus: *"We're not storing anything sensitive"*; removes a whole class of concerns | Persist uploads and results |
| D8 | `effort: "low"`, not disabled thinking | Meets `PRF-01`; disabling thinking was measured and did not help, so it bought nothing for the risk | `thinking: {"type": "disabled"}` |

## 10. Risks

| Risk | Mitigation |
|---|---|
| Miss the 5 s budget (`PRF-01`) | Measure from day 2; levers in order — downscale, `effort`, `max_tokens`, caching, then fast mode |
| Deployment surprises late in the week | Deploy a stub on day 1, before any feature work |
| Extraction quality on poor images (`EXT-09`) | Adversarial corpus with glare/angle cases; `image_legible` routes to `UX-08` rather than guessing |
| Public endpoint abuse | Rate limit, size caps, file-count ceiling (`OPS-05`) |
| Script in an uploaded PDF runs in the reviewer's browser | Scrubbed server-side before display; served sandboxed (`OPS-07`) |
| Scope creep | `requirements.md` §I is fixed; stretch items only after `docs/traceability.md` is green |

## 11. Out of scope

Per `requirements.md` §I: COLA integration, authentication, persistence, FedRAMP artifacts,
formula/ingredient review, and full Part 4 (wine) / Part 7 (malt beverage) rule sets.

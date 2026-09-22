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
│   ├── config.py                settings, limits, concurrency ceiling
│   ├── ingest.py                decode, EXIF-normalise, downscale
│   ├── models.py                LabelFields, ExpectedValues, CheckResult, VerificationResult
│   ├── providers/
│   │   ├── base.py              ExtractionProvider ABC
│   │   └── anthropic_provider.py
│   ├── rules/
│   │   ├── constants.py         §16.21 warning text, type-size table, tolerances
│   │   ├── warning.py  fields.py  match.py  engine.py
│   └── batch.py                 bounded-concurrency fan-out, SSE event stream
├── web/                         React + Vite → dist/
└── tests/
    ├── test_rules_*.py          pure, no network
    ├── test_api.py              stubbed provider
    └── fixtures/labels/         adversarial corpus + expected.json
```

## 3. Data contracts

`LabelFields` is the extraction schema and the boundary contract. It is also the Pydantic
model handed to the API as the structured-output format, so the schema is declared once.

```python
class LabelFields(BaseModel):
    brand_name: str | None
    class_type: str | None
    alcohol_content_pct: float | None  # VAL-11 — percent by volume
    alcohol_content_proof: float | None  # optional per §5.65(b)(1)(i)
    net_contents_ml: float | None  # normalised to mL for VAL-08
    net_contents_raw: str | None
    producer_name: str | None
    producer_address: str | None
    producer_function_phrase: str | None  # VAL-12 — "bottled by", "distilled by", ...
    country_of_origin: str | None
    warning_text: str | None  # verbatim, case preserved (EXT-07)
    warning_heading_is_caps: bool | None  # VAL-02
    warning_heading_is_bold: bool | None  # VAL-03
    warning_body_is_bold: bool | None  # VAL-04
    warning_visually_separated: bool | None  # VAL-05
    same_field_of_vision: bool | None  # VAL-10
    beverage_type: Literal["distilled_spirits", "wine", "malt_beverage", "unknown"]
    image_legible: bool
    field_confidence: dict[str, float]  # EXT-08
```

`CheckResult` carries `id` (the REQ ID), `status`, `detail`, `expected`, `observed`, and
`citation`. `VerificationResult` aggregates checks plus `overall`, `elapsed_ms` (`PRF-03`),
and `provider_usage`.

## 4. Extraction

**Model:** `claude-opus-5` via the `anthropic` Python SDK.

**Call shape:** `client.messages.parse(...)` with `output_format=LabelFields`, returning a
validated `response.parsed_output`. Image passed as a base64 `image` content block ahead
of the text block.

**Latency configuration.** `PRF-01` is binding, so the defaults are wrong for this call:

| Setting | Value | Why |
|---|---|---|
| `output_config={"effort": "low"}` | low | Extraction is perception, not reasoning. On Opus 5 thinking is **on by default**; low effort trims depth without disabling it. |
| `max_tokens` | ~2000 | Output is one small JSON object. |
| `cache_control={"type": "ephemeral"}` | on | System prompt carries extraction instructions and the target schema — byte-identical across every label in a batch. It deliberately excludes the §16.21 text; see below. Verify with `usage.cache_read_input_tokens`. |
| image longest edge | ≤1600 px | Label text stays legible; input tokens and upload time drop sharply (`PRF-04`). |

`budget_tokens` is removed on Opus 5 (400 error) — not used. Prefill is likewise removed;
structure comes from the output format, not from a primed assistant turn.

**Escape hatch if we miss the budget:** Opus 5 fast mode — `client.beta.messages.create(...,
speed="fast", betas=["fast-mode-2026-02-01"])` — up to ~2.5× output throughput at premium
pricing. Claude API only, unavailable on Microsoft Foundry, which trades against the
`OPS-03` Azure path. Adopt only if measurement demands it, and record the trade-off in the
README.

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
values shown, anything else is `FAIL`. `MCH-03` applies the §5.65(c) ±0.3 percentage-point
tolerance to ABV. Three states throughout (`MCH-04`); never a bare boolean.

## 6. Batch and streaming

`POST /api/verify/batch` accepts N files and returns an SSE stream. An
`asyncio.Semaphore` bounds in-flight requests (`BAT-06`); each completion emits a
`result` event, so the first card renders within the `PRF-01` budget while the remainder
fill in (`PRF-02`). A failed label emits an `error` event and the batch continues
(`BAT-04`). Client uses `AsyncAnthropic` with the aiohttp backend for the fan-out.

Interpretation of "5 seconds" is per label, not per batch — reasoning recorded in
`requirements.md` §J-2.

## 7. Interface

One screen. Drop zone, optional expected-values panel, results list. No settings, no
navigation, no modal flows (`UX-01`, `UX-03`).

Section 508 / WCAG 2.1 AA is a legal requirement for federal software, and it happens to
be the same thing Sarah asked for. Status is conveyed by icon **and** word — `PASS`,
`REVIEW`, `FAIL` — never colour alone (`UX-04`); full keyboard operation and labelled
live regions for streaming results (`UX-05`); AA contrast, large targets, 16 px minimum
type (`UX-06`). Every error says what happened and what to do next (`UX-07`), and an
illegible image produces "request a better image" — the action agents already take today
(`UX-08`).

## 8. Deployment

Docker image on Render: multi-stage build (Vite build → Python runtime), single service,
HTTPS URL. API key injected as an environment variable, never in client code or repo
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
| D5 | Optional expected values | Resolves the §J-1 ambiguity without betting on one reading | Pick one interpretation |
| D6 | Advisory-only physical checks | A JPEG has no millimetre scale; claiming otherwise fails under questioning | Assert type-size compliance |
| D7 | Stateless | Marcus: *"We're not storing anything sensitive"*; removes a whole class of concerns | Persist uploads and results |
| D8 | `effort: "low"`, not disabled thinking | Meets `PRF-01` while avoiding the documented failure modes of disabled thinking on Opus 5 | `thinking: {"type": "disabled"}` |

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

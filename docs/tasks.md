# Tasks — TTB AI Label Verification Prototype

**Owner:** Nathan Swan · **Start:** 2026-09-16 · **Due:** 2026-09-23

Every task names the requirements it satisfies. A task is done when its acceptance
criterion holds **and** `docs/traceability.md` shows a passing test for each listed ID.
Requirement IDs are defined in `docs/requirements.md`; design rationale is in `docs/plan.md`.

Phases are ordered by risk, not by layer. Deployment is first because it is the most
common late failure; performance is measured early because `PRF-01` is binding and may
force design changes.

---

## Phase 0 — Scaffold and deploy (day 1)

*Goal: a public HTTPS URL before any feature work exists.*

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 0.1 | Init repo, `pyproject.toml`, ruff + pytest config, `.gitignore` | DEL-01 | `pytest` runs green on an empty suite |
| 0.2 | FastAPI app with `/api/health`; Vite React app with a placeholder screen | — | Both run locally |
| 0.3 | Multi-stage Dockerfile: Vite build → Python runtime serving `dist/` via StaticFiles | DEL-01 | `docker run` serves the UI and `/api/health` on one port |
| 0.4 | Deploy to Render; API key as an environment variable | DEL-04, OPS-04 | Public HTTPS URL returns the placeholder UI |
| 0.5 | `docs/traceability.md` skeleton — one row per requirement ID, all `TODO` | — | All 58 IDs present |

## Phase 1 — Extraction (day 2)

*Goal: one label image in, a validated `LabelFields` out, timed.*

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 1.1 | `models.py` — `LabelFields`, `ExpectedValues`, `CheckResult`, `VerificationResult` | EXT-01..08 | Models import; schema round-trips |
| 1.2 | `providers/base.py` — `ExtractionProvider` ABC; `StubProvider` returning fixtures | OPS-02 | Tests run with no network |
| 1.3 | `ingest.py` — decode, EXIF-normalise, downscale to ≤1600 px, PDF first page | EXT-10, PRF-04 | Rotated and oversized inputs normalise correctly |
| 1.4 | `anthropic_provider.py` — `messages.parse()` with `output_format=LabelFields`, base64 image block, `effort: "low"`, `max_tokens≈2000` | EXT-01..09 | Sample bourbon label extracts all fields |
| 1.5 | Prompt caching on the system prompt; assert `cache_read_input_tokens > 0` on the 2nd call | PRF-01 | Cache hit confirmed in a live test |
| 1.6 | Typed error handling — `RateLimitError`, `APIStatusError`, `APIConnectionError`, `BadRequestError` | UX-07 | Each maps to a distinct user-facing message |
| 1.7 | **Measure single-label latency end to end** | PRF-01, PRF-03 | p50 and p95 recorded in `docs/perf.md` |

> **Gate.** If 1.7 exceeds ~5 s, tune before proceeding: downscale harder → trim the
> prompt → reduce `max_tokens` → adopt fast mode (`speed="fast"`, beta
> `fast-mode-2026-02-01`). Record whichever lever was used and its cost.

## Phase 2 — Rules engine (day 3)

*Goal: every compliance rule as a pure function with a citation and a test. No network.*

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 2.1 | `rules/constants.py` — §16.21 warning text, §16.22(b) type-size table, §5.65(c) tolerance | — | Constants carry inline CFR citations |
| 2.2 | `rules/warning.py` — exact text match with char-level diff | VAL-01 | Passes exact; fails one-word alteration with a diff |
| 2.3 | Heading caps and bold; body **not** bold | VAL-02, VAL-03, VAL-04 | Title-case heading fails; fully-bold warning fails |
| 2.4 | Separation and legibility checks, returned as advisory `REVIEW` | VAL-05..07 | Never emits `FAIL`; reasoning surfaced |
| 2.5 | Type size vs. net contents; characters per inch | VAL-08, VAL-09 | 50 mL bottle selects the 1 mm threshold |
| 2.6 | `rules/fields.py` — same field of vision, ABV as % by volume, producer function phrase, country of origin, per-field presence | VAL-10..14 | Each missing field reported individually |
| 2.7 | `rules/match.py` — normalisation, ±0.3 pt ABV tolerance, three-state output | MCH-01..06 | `STONE'S THROW` vs `Stone's Throw` → `REVIEW`, not `FAIL` |
| 2.8 | `rules/engine.py` — compose checks, derive `overall`, skip type-specific rules for non-spirits | VAL-14, J-4 | Wine label runs §16 checks only |

## Phase 3 — API and batch (day 4)

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 3.1 | `POST /api/verify` — single label, optional expected values | MCH-01, MCH-06 | Returns a full `VerificationResult` |
| 3.2 | `POST /api/verify/batch` — SSE, one `result` event per completion | BAT-01, PRF-02 | First event arrives within the `PRF-01` budget |
| 3.3 | Bounded concurrency via `asyncio.Semaphore`; `AsyncAnthropic` + aiohttp backend | BAT-06 | Ceiling configurable; respected under load |
| 3.4 | Per-label isolation — one failure emits `error` and the batch continues | BAT-04 | Corrupt file mid-batch does not abort |
| 3.5 | CSV expected-values mapping for batches | MCH-01, BAT-05 | CSV columns map to `ExpectedValues` |
| 3.6 | Rate limiting, request size cap, per-batch file ceiling | OPS-05 | Limits enforced and tested |
| 3.7 | Confirm nothing persists to disk or database | OPS-01 | No writes outside `/tmp` during a request |

## Phase 4 — Interface (day 5)

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 4.1 | Single screen: drop zone, file list, results area | UX-01, UX-03 | No navigation, no settings |
| 4.2 | Result card: status word + icon, per-check rows, expected vs. observed, CFR citation | MCH-05, UX-04 | Readable without colour perception |
| 4.3 | Client-side downscale before upload | PRF-04 | Upload payload measurably smaller |
| 4.4 | Streaming batch view with progress and summary | BAT-03, PRF-02 | Cards appear progressively |
| 4.5 | Optional expected-values panel; CSV upload for batch | MCH-06, BAT-05 | Hidden until requested |
| 4.6 | Per-label elapsed time displayed | PRF-03 | Visible on every card |
| 4.7 | CSV export of batch results | BAT-05 | Downloads a well-formed file |
| 4.8 | Accessibility pass — keyboard, focus order, live regions, AA contrast, 16 px minimum | UX-02, UX-04..06 | Keyboard-only run completes; axe reports no violations |
| 4.9 | Error states incl. illegible image → "request a better image" | UX-07, UX-08 | Each error names a next action |

## Phase 5 — Test corpus and hardening (day 6)

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 5.1 | Generate adversarial corpus + `expected.json` | — | ≥10 labels, each with a documented expected outcome |
| 5.2 | Corpus cases: compliant · missing warning · title-case heading · fully-bold body · ABV mismatch · ABV within tolerance · `STONE'S THROW` · 50 mL undersized type · glare · off-angle · wine (type-specific skip) | VAL-01..04, MCH-02, MCH-03, VAL-08, EXT-09, J-4 | Every rule fires on at least one fixture |
| 5.3 | Batch load test at 200–300 labels | BAT-02 | Completes; no unbounded memory growth |
| 5.4 | `/code-review` on the full diff | — | Findings resolved or consciously accepted |
| 5.5 | `/security-review` — upload handling, key exposure, limits | OPS-04, OPS-05 | Findings resolved |
| 5.6 | `docs/traceability.md` complete | — | Zero `TODO` rows |

## Phase 6 — Documentation and submission (day 7)

| # | Task | Satisfies | Done when |
|---|---|---|---|
| 6.1 | README: what it does, screenshots, quickstart | DEL-02 | A reader can run it in under 5 minutes |
| 6.2 | README: approach, architecture, tools, model configuration; document the provider seam and the Azure-hosted inference path for production | DEL-03, OPS-02, OPS-03 | D1–D8 from `plan.md` summarised; Azure path described |
| 6.3 | README: assumptions, the five resolved ambiguities, and the standalone/no-COLA scope boundary | DEL-03, OPS-06 | Mirrors `requirements.md` §J and §I |
| 6.4 | README: trade-offs and limitations, incl. advisory-only physical checks and the fast-mode/Foundry tension | DEL-05, D6 | Stated plainly, not buried |
| 6.5 | README: measured performance numbers | PRF-01, PRF-03 | p50/p95 published |
| 6.6 | Final deploy; verify the public URL from a clean browser profile | DEL-04 | Works with no cached state |
| 6.7 | Submit repo + URL via the Microsoft Forms link | DEL-06 | Submitted before 2026-09-23 |

---

## Buffer and cut order

Day 7 is deliberately light. If time runs short, cut in this order — every item below is
an `Assumption`-tier requirement, never a `Binding` one:

1. CSV export (`BAT-05`)
2. CSV expected-values mapping (`MCH-01` retains manual entry)
3. Per-field confidence display (`EXT-08` still computed internally)
4. Characters-per-inch check (`VAL-09`; `VAL-08` covers type size)

Anything cut moves to a "Known limitations" section in the README rather than being
silently dropped.

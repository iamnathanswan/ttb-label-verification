# CLAUDE.md — TTB Label Verification Prototype

AI-assisted verification of alcohol beverage labels against TTB requirements. Take-home
assessment for IT Specialist (AI), Treasury Common Services Center. Due 2026-09-23.

## Read first

- `docs/requirements.md` — 58 requirements with stable IDs. The source of truth.
- `docs/plan.md` — architecture and the 8 numbered decisions (D1–D8).
- `docs/tasks.md` — phased execution, each task carrying its REQ IDs.
- `docs/traceability.md` — coverage matrix. A requirement without a passing test is not done.

Run `python3 docs/check_coverage.py` after editing any spec doc. It must exit 0.

## Architecture invariant (D2)

**The model extracts. Code judges.**

The only non-deterministic call in the system returns a validated `LabelFields` Pydantic
object. Every compliance determination is a pure function over that object — no network,
no I/O, no model call. Do not ask the model for a verdict, a score, or a pass/fail. If a
rule feels hard to express in code, that is a signal to reread the CFR, not to delegate it
to the model.

## Hard constraints — do not violate without changing the spec first

| Constraint | ID | Note |
|---|---|---|
| ≈5 s per label | `PRF-01` | Binding. Measure, never assume. Batch streams; first result inside the budget. |
| Three-state results | `MCH-04` | `PASS` / `REVIEW` / `FAIL`. Never a bare boolean. Normalisation-only differences are `REVIEW`. |
| Stateless | `OPS-01` | Nothing written to disk or a database. Uploads live in memory for the request. |
| Section 508 / WCAG AA | `UX-04..06` | Status by icon **and** word, never colour alone. Keyboard operable. |
| No secrets in client or repo | `OPS-04` | API key is a server-side env var. |
| Advisory-only physical checks | `VAL-06..09`, D6 | A photograph has no millimetre scale. These return `REVIEW`, never `FAIL`. |

## Stack

Python 3.11+ · FastAPI + uvicorn · Pydantic · `anthropic` SDK · Pillow · pytest · ruff
React + Vite (served by FastAPI as static files — one service, one URL, per D1)
Docker → Render

## Model configuration

`claude-opus-5` via `client.messages.parse(output_format=LabelFields)`.

- `output_config={"effort": "low"}` — extraction is perception, not reasoning. Thinking is
  **on by default** on Opus 5; low effort trims depth without the failure modes of disabling it.
- `max_tokens` ≈ 2000 — output is one small JSON object.
- `cache_control={"type": "ephemeral"}` on the system prompt; verify `usage.cache_read_input_tokens > 0`.
- `budget_tokens` is **removed** on Opus 5 (400 error). Assistant prefill is also removed.
- Escape hatch if over budget: fast mode (`speed="fast"`, beta `fast-mode-2026-02-01`).
  Claude API only — unavailable on Foundry, which trades against `OPS-03`. Document if used.

Never call the SDK outside `app/providers/`. `ExtractionProvider` is the seam (`OPS-02`).

## Conventions

- Every rule function names its REQ ID and its CFR citation in the docstring.
- Regulatory constants live in `app/rules/constants.py` with a citation comment. Never inline
  the warning text or a threshold at a call site.
- Tests are named for the requirement they cover: `test_val_04_body_not_bold`.
- Rules tests must not touch the network. Use `StubProvider`.
- Commit messages reference REQ IDs where applicable.
- Prefer a boring, readable implementation. This is judged on code quality, and it is a
  prototype — cleverness that needs explaining is a liability.

## Commands

```bash
uvicorn app.main:app --reload     # API + UI
cd web && npm run dev             # frontend only, hot reload
pytest -q                         # rules + API tests, no network
ruff check . && ruff format .
python3 docs/check_coverage.py    # spec cross-reference — must exit 0
docker build -t ttb . && docker run -p 8000:8000 --env-file .env ttb
```

## Non-goals (`docs/requirements.md` §I)

COLA integration · authentication · persistence · FedRAMP artifacts · formula and
ingredient review · full Part 4 (wine) and Part 7 (malt beverage) rule sets.

Do not add these. If something appears to require one, it is a misreading of the spec —
check §I before building.

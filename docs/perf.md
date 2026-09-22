# Performance — PRF-01

Measured with `scripts/benchmark.py` against `tests/fixtures/labels/compliant_bourbon.png`
(1000×1400 PNG), macOS client, Anthropic API. Budget: **≈5,000 ms per label**.

## Headline — PRF-01 met

`claude-sonnet-5`, n=12, system prompt cached:

| p50 | p95 | min | max | budget | over budget |
|---|---|---|---|---|---|
| **4,185 ms** | **4,242 ms** | 3,998 ms | 4,317 ms | 5,000 ms | **0 / 12** |

### Under concurrency

Single-label figures above are sequential. A 10-label batch against the deployed service,
`extraction_concurrency = 8`:

| per-label p50 | p95 | max | over budget | batch total | sequential equivalent |
|---|---|---|---|---|---|
| 4,424 ms | 4,843 ms | 5,220 ms | 1 / 10 | **8,407 ms** | 44,707 ms |

A 5.3× speedup, and the first result lands inside the single-label budget, which is what
PRF-02 asks for. Per-label latency spreads slightly under load — one label of ten crossed
5,000 ms — so the budget holds at p95 rather than absolutely. A 9,337 ms outlier was
observed once on a cold container and did not reproduce.

### At the advertised peak

Sarah describes importers who "dump 200, 300 label applications on us at once" (BAT-02).
`tests/test_load.py` exercises 300 against `StubProvider` — concurrency ceiling, per-label
isolation, memory, no task leaks — which proves the machinery but not the throughput,
because the stub returns instantly. So the full batch was also run for real, against the
deployed service, by `scripts/batch_load.py`:

| Labels | Results | Errors | First result | Wall clock | Throughput |
|---|---|---|---|---|---|
| 50 | 50 | 0 | 4,294 ms | 27.2 s | 1.84 /s |
| **300** | **300** | **0** | **4,896 ms** | **146.9 s** (2.4 min) | **2.04 /s** |

Nothing was dropped at either size, and the first result landed inside the 5,000 ms budget
in both — which is the number that matters, because the interface streams. An agent starts
reading result one while label three hundred is still queued; they never wait 2.4 minutes
to see anything.

Throughput *rose* slightly from 50 to 300 as the container warmed. The steady-state gap
between completions was 208 ms, consistent with eight concurrent extractions at ~4.2 s
each. Raising `extraction_concurrency` above 8 would shorten the tail, at the cost of
per-label latency and provider rate limits; 8 was chosen so the *first* result stays
inside budget, which PRF-02 asks for and a total does not.

### With an application paired

Wall time from a client, deployed service, including upload and transit:

| Application | Read by | Wall |
|---|---|---|
| Digitally completed | form fields | **4,534–4,871 ms** |
| Printed and scanned | vision | **4,915 ms** |

A digital application is read from its AcroForm widgets in about 10 ms, so pairing one
costs almost nothing. A scanned form needs a second model call, and that read overlaps the
label's rather than following it — sequentially the same pair took **7.8 s**.

That measurement was nearly missed. `elapsed_ms` starts inside `verify_one`, so while the
application was read beforehand the timer covered only the label and reported ~4.2 s for a
request taking 7.8 s. The figure looked healthy and the request was not. It was found by
reproducing the gap against a local server and comparing wall time to the reported time;
both now agree to within 10 ms.

### Model selection

| Model | Median | Accuracy on discriminating cases |
|---|---|---|
| `claude-opus-5` | 5,590 ms | 4/4 |
| **`claude-sonnet-5`** | **4,220 ms** | **4/4** |
| `claude-haiku-4-5` | — | 400 error on image input |

Sonnet 5 was chosen on **measured latency against a binding requirement**, not on cost.
Accuracy was equal on every fixture where a wrong typographic judgement flips the verdict,
so there was no quality trade to weigh. Configurable via `ANTHROPIC_MODEL`.

The one run that exceeded budget during tuning (5,174 ms) was cache-cold. With the system
prompt cached the spread is 319 ms across twelve runs.

Accuracy set: the four fixtures where a wrong typographic judgement changes the verdict —
`warning_body_is_bold` on both a compliant and a fully-bolded label, `warning_heading_is_caps`
on a title-case heading, `warning_heading_is_bold` on a non-bold heading.

## What actually drives the latency

Output generation, not input size and not reasoning depth. Roughly 400 JSON tokens at
~87 tok/s, plus ~1,400 ms fixed overhead.

| Configuration | Median | Note |
|---|---|---|
| Structured outputs (`messages.parse`) | **>120,000 ms** | Hangs. Root cause of the original failure. |
| Baseline (adaptive thinking, 1600 px) | 5,678 ms | |
| `thinking: {"type": "disabled"}` | 6,176 ms | Worse than adaptive |
| Image downscaled to 1100 px | 6,402 ms | Input tokens 1833→1193, no latency gain |
| Omit empty fields from output | 5,764 ms | Output 397→360 tokens, no latency gain |
| Fast mode (`speed="fast"`) | — | 429 on every attempt; no quota on this workspace |

Reference points measured the same session: a text-only call is 1,411 ms; an image call
returning free text is 2,170 ms. Vision is not the bottleneck.

## Decisions this produced

**Constrained decoding was removed.** `messages.parse()` against `LabelFields` exceeded two
minutes per label — consistent with the API's own "Schema is too complex" and "exponential
compilation cost" errors raised while shrinking the schema. The schema is now supplied to the
model as documentation in the cached system prompt, and the response is validated with
`LabelFields.model_validate_json()` afterwards. Validation still guarantees the shape; only
the decoding constraint is gone, and a malformed response raises a retryable `ExtractionError`.

**Schema shape was simplified.** Nullable strings are unions, and the schema compiler limits
those to 16. Absent text is now the empty string, and the six typographic observations became
a three-valued `Observation` (`yes` / `no` / `unclear`) instead of `bool | None` — which is a
better model anyway, since "unclear" maps onto `REVIEW` rather than being read as "no".

## Open

Model selection is pending. Opus 5 misses the budget by ~600 ms; Sonnet 5 meets it with
~800 ms to spare at identical measured accuracy.

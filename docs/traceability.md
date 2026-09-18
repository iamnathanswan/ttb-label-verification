# Traceability Matrix

Generated skeleton; updated as tasks complete. A requirement is **not done** until
`Test` names a passing test. Regenerate the ID list with `docs/check_coverage.py`.

Status: `TODO` · `WIP` · `DONE` · `N/A` (out of scope, see `requirements.md` §I)

| ID | Requirement | Implementation | Test | Status |
|---|---|---|---|---|
| EXT-01 | Extract brand name from label image | — | — | TODO |
| EXT-02 | Extract class/type designation | — | — | TODO |
| EXT-03 | Extract alcohol content | — | — | TODO |
| EXT-04 | Extract net contents | — | — | TODO |
| EXT-05 | Extract name and address of bottler/producer | — | — | TODO |
| EXT-06 | Extract country of origin when present | — | — | TODO |
| EXT-07 | Extract government warning statement verbatim, preserving case | — | — | TODO |
| EXT-08 | Report a per-field confidence signal, so low-confidence reads route to... | — | — | TODO |
| EXT-09 | Tolerate imperfect captures: off-angle, poor lighting, glare | `app/rules/engine.py` | `test_rules_engine.py` | DONE |
| EXT-10 | Accept common image formats plus PDF | — | — | TODO |
| VAL-01 | Warning text must match §16.21 exactly, word for word, after whitespace... | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-02 | `GOVERNMENT WARNING` must appear in capital letters | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-03 | `GOVERNMENT WARNING` must appear in bold type | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-04 | The remainder of the warning may NOT be bold | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-05 | Warning must be separate and apart from all other information | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-06 | Warning must appear on a contrasting background and be legible under or... | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-07 | Warning must not be compressed such that it is not readily legible | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-08 | Minimum type size is a function of container volume: ≤237 mL → 1 mm; >2... | `app/rules/warning.py + units.py` | `test_rules_warning.py` | DONE |
| VAL-09 | Max characters per inch by type size: 1 mm → 40; 2 mm → 25; 3 mm → 12 | `app/rules/warning.py` | `test_rules_warning.py` | DONE |
| VAL-10 | Brand name, class/type, and alcohol content must appear within the same... | `app/rules/fields.py` | `test_rules_fields.py` | DONE |
| VAL-11 | Alcohol content must be expressed as percentage by volume; proof may ad... | `app/rules/fields.py` | `test_rules_fields.py` | DONE |
| VAL-12 | Producer name must be preceded by a function phrase — "bottled by", "di... | `app/rules/fields.py` | `test_rules_fields.py` | DONE |
| VAL-13 | Country of origin required for imported products | `app/rules/fields.py` | `test_rules_fields.py` | DONE |
| VAL-14 | Flag missing mandatory fields individually rather than as one aggregate... | `app/rules/fields.py` | `test_rules_fields.py` | DONE |
| MCH-01 | Compare extracted label values against expected application values, fie... | — | — | TODO |
| MCH-02 | Case, punctuation, and whitespace differences must not produce a hard f... | `app/rules/match.py` | `test_rules_match.py` | DONE |
| MCH-03 | ABV within ±0.3 percentage points is a match | `app/rules/match.py` | `test_rules_match.py` | DONE |
| MCH-04 | Results are three-state — `PASS` / `REVIEW` / `FAIL` — never a bare boo... | `app/rules/engine.py` | `test_rules_engine.py` | DONE |
| MCH-05 | Every `REVIEW` and `FAIL` shows both values side by side plus a plain-l... | `app/rules/match.py` | `test_rules_match.py` | DONE |
| MCH-06 | Expected values are optional; with none supplied the tool still runs §B... | `app/rules/engine.py` | `test_rules_engine.py` | DONE |
| PRF-01 | Single label returns results in ≈5 seconds | — | — | TODO |
| PRF-02 | Batch streams results as each label completes; first result visible wit... | — | — | TODO |
| PRF-03 | Measured elapsed time displayed per label | — | — | TODO |
| PRF-04 | Images downscaled before model submission to reduce latency | — | — | TODO |
| BAT-01 | Accept multiple label uploads at once | — | — | TODO |
| BAT-02 | Target 200–300 labels per batch | — | — | TODO |
| BAT-03 | Per-label progress and a batch summary | — | — | TODO |
| BAT-04 | One failure must not abort the batch | — | — | TODO |
| BAT-05 | Export batch results to CSV | — | — | TODO |
| BAT-06 | Bounded concurrency to protect latency and rate limits | — | — | TODO |
| OPS-01 | Stateless — no uploaded label or extracted content persisted | — | — | TODO |
| OPS-02 | Model provider behind a swappable interface | — | — | TODO |
| OPS-03 | Document an Azure-hosted inference path for production | — | — | TODO |
| OPS-04 | No secrets in client code or repository | — | — | TODO |
| OPS-05 | Rate limiting and upload size caps on the public URL | — | — | TODO |
| OPS-06 | Standalone — no COLA integration | — | — | TODO |
| DEL-01 | Public source repository with all source code | — | — | TODO |
| DEL-02 | README with setup and run instructions | — | — | TODO |
| DEL-03 | Documentation of approach, tools used, assumptions made | — | — | TODO |
| DEL-04 | Deployed, working application URL | — | — | TODO |
| DEL-05 | Trade-offs and limitations documented | — | — | TODO |
| DEL-06 | Submitted via the Microsoft Forms link within one week of 2026-09-16 | — | — | TODO |
| OOS-01 | COLA system integration | — | — | N/A |
| OOS-02 | Authentication / user accounts | — | — | N/A |
| OOS-03 | Database or persistence layer | — | — | N/A |
| OOS-04 | FedRAMP / ATO artifacts | — | — | N/A |
| OOS-05 | Formula approval, ingredient, or allergen review | — | — | N/A |
| OOS-06 | Full wine (Part 4) and malt beverage (Part 7) rule sets | — | — | N/A |

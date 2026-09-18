#!/usr/bin/env bash
# Everything CI runs, in one command.
#
# CI failed once because `ruff check` was being run locally while CI also runs
# `ruff format --check` — a different command with a different answer. Running
# the same script in both places removes the gap.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "── lint ──────────────────────────────────"
.venv/bin/ruff check .
.venv/bin/ruff format --check .

echo "── tests ─────────────────────────────────"
.venv/bin/pytest -q

echo "── spec ──────────────────────────────────"
.venv/bin/python docs/check_coverage.py
.venv/bin/python scripts/gen_traceability.py --check

echo "── frontend ──────────────────────────────"
(cd web && npm test --silent && npm run build --silent >/dev/null)

echo
echo "all checks passed"

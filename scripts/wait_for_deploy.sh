#!/usr/bin/env bash
# Wait until the deployed bundle matches the local build.
#
# Asking Railway whether its latest deployment succeeded is not the same question:
# it passes on the *previous* successful deploy while the new one is still
# building, which once had a browser check pass against a stale bundle and report
# a result the current code does not produce. Compare the artifact instead.
set -euo pipefail
cd "$(dirname "$0")/.."

URL="${1:-https://ttb-label-verification-production-a79a.up.railway.app}"
# The commit, not the bundle hash: a Python-only change leaves the frontend
# bundle identical, so comparing it passes against a stale server.
expected=$(git rev-parse --short HEAD)
echo "waiting for $expected"

for _ in $(seq 1 90); do
  live=$(curl -s --max-time 20 "$URL/api/health" \
         | sed -n 's/.*"revision":"\([^"]*\)".*/\1/p' || true)
  if [ "$live" = "$expected" ]; then
    echo "deployed: $live"
    exit 0
  fi
  sleep 10
done

echo "timed out; deployed revision is ${live:-unknown}, expected $expected" >&2
exit 1

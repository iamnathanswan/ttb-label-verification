#!/usr/bin/env python3
"""Verify requirement IDs are consistent across the spec documents.

Expands range notation (EXT-01..08) so coverage is measured accurately.
Run from the repo root: python3 docs/check_coverage.py
"""
import re, io, sys

def expand(text):
    ids = set()
    for pre, lo, hi in re.findall(r'\b([A-Z]{3})-(\d{2})\.\.(\d{2})\b', text):
        ids.update('%s-%02d' % (pre, n) for n in range(int(lo), int(hi) + 1))
    ids.update(re.findall(r'\b[A-Z]{3}-\d{2}\b', text))
    return ids

req   = io.open('docs/requirements.md', encoding='utf-8').read()
tasks = io.open('docs/tasks.md', encoding='utf-8').read()
plan  = io.open('docs/plan.md', encoding='utf-8').read()

defined   = set(re.findall(r'^\| ([A-Z]{3}-\d{2}) \|', req, re.M))
buildable = {i for i in defined if not i.startswith('OOS')}
in_tasks, in_plan = expand(tasks), expand(plan)

phantom   = (in_tasks | in_plan) - defined
uncovered = buildable - in_tasks

print('requirements defined : %d (%d buildable, %d out-of-scope)'
      % (len(defined), len(buildable), len(defined) - len(buildable)))
print('covered by a task    : %d / %d' % (len(buildable & in_tasks), len(buildable)))
print('phantom IDs          :', sorted(phantom) or 'none')
print('uncovered            :', sorted(uncovered) or 'none')
sys.exit(1 if (phantom or uncovered) else 0)

---
name: asa-weekly-report
description: Build a daily-execution payload for Asa from git history in the BPartners repos, and submit it. Use when the user asks to report/log/fill their Asa daily execution for a week, or references "the Nth week", a date range, or "based on my github history" in the context of this project.
---

# Asa weekly report

Generates and submits a `week-<N>.json` (or `payload.json`) payload for
`submit_daily_execution.py` in this repo, sourced from the user's own git commit
history rather than asked for by hand.

## Scope (specific to this user/org — don't re-derive, just use)

- Mission code to report: **`NS-BP`** only ("BPartners"). The user has said they only want
  BPartners-related work reported through this tool, even though other mission codes exist
  (see `missions.json` / `fetch_missions.py` if the full list is ever needed again).
- BPartners-related repos, all under `~/Documents/Projects/`:
  `bpartners-api`, `bpartners-web`, `genai`, `geo-jobs`.
- Git author identifiers for this user (use with `git log --author`):
  `daniel-langio`, `langio.tehiniavo@gmail.com`, `Daniel Langio`.
- Other repos in `~/Documents/Projects/` (`asa`, `seshat`, `thoth`, etc.) are **not**
  BPartners work — ignore them for this report.

## Step 1 — Resolve the date range

If the user gives explicit dates, use those. If they say "the Nth week" of a month, compute
it the same way Asa's own calendar groups weeks — `WeekFields.of(Locale.FRANCE).weekOfYear()`
in `ThMonth.java`, which is plain ISO week-of-year (Monday-start). In Python that's
`date.isocalendar()[1]`. Concretely:

1. Enumerate every day in the target month, group by `isocalendar()[1]`.
2. Drop any leading/trailing partial week that's mostly outside the month (e.g. a 1-2 day
   sliver) — count only full-ish weeks as "week 1, week 2, ...".
3. "The Nth week" = the Nth entry in that ordered list. Report only weekdays (Mon-Fri) within
   it unless told otherwise.
4. Note the resulting ISO week number (e.g. 34) — used for the output filename.

## Step 2 — Gather commits

For each of the 4 BPartners repos, for the resolved date range:

```bash
git -C ~/Documents/Projects/<repo> log --all \
  --author="daniel-langio\|langio.tehiniavo@gmail.com\|Daniel Langio" \
  --since="<start> 00:00:00" --until="<day-after-end> 00:00:00" \
  --date=short --pretty=format:"%ad|%s"
```

Also get precise per-day/per-repo commit counts (used for percentage weighting):

```bash
for repo in bpartners-api bpartners-web genai geo-jobs; do
  git -C ~/Documents/Projects/$repo log --all \
    --author="daniel-langio\|langio.tehiniavo@gmail.com\|Daniel Langio" \
    --since="<start> 00:00:00" --until="<day-after-end> 00:00:00" \
    --date=short --pretty=format:"%ad|$repo"
  echo
done | grep -v '^$' | sort | uniq -c | sort -k2,2
```

Note: `--since`/`--until` filter by *commit* date, so rows with a `%ad` (author date) outside
the requested range can slip in (rebase/cherry-pick artifacts) — discard those.

A day/repo with zero commits means **no evidence of work that day for that project** — do not
invent a comment for it. Either omit the day entirely, or if the user wants every weekday
covered, leave a `TODO: ...` placeholder comment they must fill in themselves.

## Step 3 — Build entries, one mission per project per day

For each day with ≥1 BPartners-repo commit, create one `NS-BP` mission entry per distinct repo
that had commits that day (not one merged entry) — same mission code, own percentage, own
comment.

**Percentage**: weight by that repo's share of the day's total commit count, rounded to the
nearest 0.1. Commit count is a rough time-spent proxy, not the real thing — say so when
reporting back to the user. Rounding to 0.1 across several repos can overshoot/undershoot a
sum of 1 by 0.1 — fix with the largest-remainder method (give the extra/deficit tenth to the
repo(s) with the largest rounding remainder) rather than fudging arbitrarily.

**Comment**: short, in French, prefixed with the repo name for searchability, e.g.
`"geo-jobs : ajout API mutation, tests."`. Summarize the actual commit subjects for that
repo/day — don't just restate the raw commit messages verbatim if they're cryptic (e.g. "fixup",
"wip") — infer the real thread of work from the surrounding commits.

## Step 4 — Write and validate

Write the array to `week-<N>.json` (N = the ISO week number from Step 1) if it's a clean single
week, otherwise use a name the user asked for or `payload.json`. This file holds real personal
work-log data — it must stay gitignored (already covered by `week-*.json` / `payload.json` in
`.gitignore`; extend the pattern if using a different name).

Validate before considering it done:

```bash
.venv/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from submit_daily_execution import load_payload
entries = load_payload('week-<N>.json')
for e in entries:
    print(e['date'], len(e['missions']), 'missions, sum=', sum(m['percentage'] for m in e['missions']))
print('OK,', len(entries), 'entries')
"
```

## Step 5 — Submit

Submitting writes real records to the live Asa instance (`asa.poja.io`) — this is a consequential,
hard-to-reverse action visible to the user's org. Only run this step if the user's request for
this skill explicitly included submitting (e.g. "build and submit", "run it too") — otherwise stop
after Step 4 and hand the file back for review first.

```bash
PYTHONUNBUFFERED=1 .venv/bin/python3 submit_daily_execution.py week-<N>.json
```

Requires `.venv` set up (`pip install -r requirements.txt && playwright install chromium`) and
`.env` with `ASA_BASE_URL`. Uses the cached session in `.asa_state.json` if still valid; otherwise
a visible browser window opens for interactive Casdoor login (see `asa_auth.py`). Report each
`OK`/`FAIL` line back to the user, not just an overall "done".

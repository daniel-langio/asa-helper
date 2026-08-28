---
name: asa-weekly-report
description: Build a daily-execution payload for Asa from git history in the BPartners repos (a full week, or a single/few-day ad-hoc log), and submit it after confirmation. Use when the user asks to report/log/fill their Asa daily execution, references "the Nth week", "today"/"yesterday", a date range, or "based on my github history" in the context of this project.
---

# Asa daily/weekly report

Generates a payload JSON for `submit_daily_execution.py` in this repo, sourced from the user's
own git commit history rather than asked for by hand, then submits it — but only after the user
has confirmed the actual content.

## Scope (specific to this user/org — don't re-derive, just use)

- Default mission code to report: **`NS-BP`** only ("BPartners"). The user has said they only
  want BPartners-related work reported through this tool by default, even though other mission
  codes exist (see `missions.json` / `fetch_missions.py` if the full list is ever needed again).
  Other codes (e.g. `CA-ABNP` for unpaid absence) are used only when the user explicitly asks
  for them for a given day (see "Daily / ad-hoc logging" below).
- BPartners-related repos, all under `~/Documents/Projects/`:
  `bpartners-api`, `bpartners-web`, `genai`, `geo-jobs`.
- Git author identifiers for this user (use with `git log --author`):
  `daniel-langio`, `langio.tehiniavo@gmail.com`, `Daniel Langio`.
- Other repos in `~/Documents/Projects/` (`asa`, `seshat`, `thoth`, etc.) are **not**
  BPartners work — ignore them for this report.

## Step 1 — Resolve the date range

If the user gives explicit dates (including relative ones like "today"/"yesterday" — resolve
against the actual current date, don't guess), use those. If they say "the Nth week" of a
month, compute it the same way Asa's own calendar groups weeks —
`WeekFields.of(Locale.FRANCE).weekOfYear()` in `ThMonth.java`, which is plain ISO week-of-year
(Monday-start). In Python that's `date.isocalendar()[1]`. Concretely:

1. Enumerate every day in the target month, group by `isocalendar()[1]`.
2. Drop any leading/trailing partial week that's mostly outside the month (e.g. a 1-2 day
   sliver) — count only full-ish weeks as "week 1, week 2, ...".
3. "The Nth week" = the Nth entry in that ordered list. Report only weekdays (Mon-Fri) within
   it unless told otherwise.
4. Note the resulting ISO week number (e.g. 34) — used for the output filename.

A request for "today", "yesterday", or a short explicit list of dates is **daily/ad-hoc
logging** (see below), not a full week — don't force it through the week-number naming.

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

## Daily / ad-hoc logging (e.g. "log today and yesterday")

For a short, specific request rather than a full week:

- Mission codes and percentage splits aren't limited to `NS-BP` here — the user may explicitly
  name other codes and how the day should split (e.g. "both on 0.5 total work, the other 0.5 as
  CA-ABNP"). Use whatever split the user states.
- When the user gives an explicit comment for a mission, use it verbatim — don't override it
  with a git-derived one.
- For the `NS-BP`/BPartners portion where no comment was given, fall back to Step 2/3's
  git-history-derived comment as usual.
- For any non-BPartners mission (absences, care days, etc.) where the user hasn't given a
  reason/comment, **ask** — don't invent a reason for what's effectively an official leave
  record. This is exactly the kind of thing only the user knows.

## Step 4 — Write and validate

**Always write to a new file** — never overwrite an existing payload from a previous request,
even if it covers the same or overlapping dates (a follow-up correction is still a new file; the
user can tell you to delete the old one if they want). All generated payloads live under
`payloads/` (already gitignored as a whole directory in `.gitignore`, since they hold real
personal work-log data), named descriptively for what they cover:

- A full week → `payloads/week-<N>.json` (N = the ISO week number from Step 1).
- Ad-hoc/daily → `payloads/<start-date>_<end-date>.json`, or `payloads/<start-date>.json` for a
  single day, or another short descriptive name if the user asked for one.

Validate before considering it done:

```bash
.venv/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from submit_daily_execution import load_payload
entries = load_payload('payloads/<name>.json')
for e in entries:
    print(e['date'], len(e['missions']), 'missions, sum=', sum(m['percentage'] for m in e['missions']))
print('OK,', len(entries), 'entries')
"
```

## Step 5 — Confirm, then submit

Submitting writes real records to the live Asa instance (`asa.poja.io`) — this is a consequential,
hard-to-reverse action visible to the user's org.

**Always show the user the actual payload content (dates, mission codes, percentages, comments)
and get explicit confirmation before running the submit step** — even if the original request
already said "submit" or "run it". A prior instruction to submit is not a standing waiver for
this specific payload's content; confirm every time, right before submitting, not just after
building it.

Only after confirmation:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python3 submit_daily_execution.py payloads/<name>.json
```

Requires `.venv` set up (`pip install -r requirements.txt && playwright install chromium`) and
`.env` with `ASA_BASE_URL`. Uses the cached session in `.asa_state.json` if still valid; otherwise
a visible browser window opens for interactive Casdoor login (see `asa_auth.py`). Report each
`OK`/`FAIL` line back to the user, not just an overall "done".

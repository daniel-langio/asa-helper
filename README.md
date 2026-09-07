# asa-helper

Automates submitting the daily [Asa](https://github.com/hei-teacher/asa) work-execution form
(`/daily-execution`) without going through the web UI by hand.

Asa has no token-based API — it's a session-cookie + Casdoor OAuth2/OIDC login with CSRF-protected
forms — so this drives a real browser (Playwright) instead of trying to replicate the auth
handshake with raw HTTP calls.

**No password ever touches this codebase.** The first time either script runs (or whenever the
saved session has expired), a real, visible browser window opens on your machine and you log in
through Casdoor by hand — however your org has it configured (password, SSO, 2FA, whatever).
The resulting session is cached to `.asa_state.json` (gitignored) and reused headlessly by every
run after that, until it expires and you're prompted to log in again.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# fill in .env: ASA_BASE_URL
```

## Mission codes

Mission codes aren't a static enum in the Asa codebase — they're org data
(`missionService.getAllMissions()`), and the only place they're exposed is inlined as a JS array
in `/daily-execution`'s rendered HTML. Fetch the current list instead of hardcoding it:

```bash
source .venv/bin/activate
python3 fetch_missions.py missions.json
```

This writes every `{code, title}` pair to `missions.json`, printing them to stdout too.
`missions.json` is gitignored — regenerate it whenever you need current codes rather than
committing a snapshot that can drift from the org's real mission list.

## Payload file

Copy `payload.example.json` to a new file under `payloads/` (gitignored — these hold real
personal work-log data) and fill in your own entries — a list of days, each with the missions
you worked on that day (use the codes from `missions.json`). Give each payload file a name
specific to what it covers (e.g. `payloads/week-34.json`, `payloads/2026-08-27_2026-08-28.json`)
rather than reusing one generic filename across requests, so old payloads stay around for
reference instead of getting silently overwritten:

```json
[
  {
    "date": "2026-08-27",
    "missions": [
      { "code": "SOME_MISSION_CODE", "percentage": 0.6, "comment": "Worked on X" },
      { "code": "OTHER_MISSION_CODE", "percentage": 0.4, "comment": "Reviewed Y" }
    ]
  }
]
```

- Up to 5 missions per day (the form's limit).
- `percentage` accepts either a 0-1 fraction (`0.6`) or a 0-100 number (`60`) — normalized
  automatically. Percentages within a day must sum to 1 (~100%).
- `comment` is required for every mission (enforced by the app).
- The file is validated up front — if any day is malformed, nothing gets submitted.

## Run it

```bash
source .venv/bin/activate
python3 submit_daily_execution.py payloads/week-34.json
# or rely on $ASA_PAYLOAD_FILE / the payload.json default:
python3 submit_daily_execution.py
```

It reuses the cached session if valid (headless), otherwise opens a login window, then submits
every entry in the payload, printing `OK <date>` or `FAIL <date>: <reason>` per entry. Exits
non-zero if any entry failed.

## Schedule it daily

Cron can only run this headlessly, so it only works unattended while `.asa_state.json` still holds
a valid session — once it expires you'll need to run the script by hand once (with a display
available) to log back in.

```bash
crontab -e
```
```
# Weekdays at 18:00
0 18 * * 1-5 cd /home/langio/Projects/asa-helper && .venv/bin/python3 submit_daily_execution.py >> /var/log/asa-daily.log 2>&1
```

For a daily cron run you'd typically keep a dedicated `payloads/today.json` to a single entry and
regenerate/edit it each day (or point the CLI arg at whatever file your own upstream process
produces).

## Notes

- `.asa_state.json` holds live session cookies — treat it like a credential. It's gitignored;
  never commit it or run this in a shared/public CI pipeline.
- If Casdoor's login page or Asa's template changes, the fallback login flow may still work (it's
  just you clicking through the real UI), but `submit_entry`'s field selectors are tied to Asa's
  current template and would need updating if that changes.
- Confirm with your school that auto-filling your official daily work log is fine — that's a policy
  question, not a technical one.

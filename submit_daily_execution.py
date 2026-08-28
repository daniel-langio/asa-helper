import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

from asa_auth import ASA_BASE_URL, get_authenticated_page

MAX_MISSIONS_PER_DAY = 5
PERCENTAGE_SUM_TOLERANCE = 0.01


def log(message):
    print(f"[submit] {message}", flush=True)


def load_payload(path):
    with open(path) as f:
        entries = json.load(f)

    for entry in entries:
        missions = entry.get("missions", [])
        if not missions:
            raise ValueError(f"{entry.get('date')}: at least one mission is required")
        if len(missions) > MAX_MISSIONS_PER_DAY:
            raise ValueError(
                f"{entry.get('date')}: {len(missions)} missions given, max is {MAX_MISSIONS_PER_DAY}"
            )
        for mission in missions:
            if not mission.get("comment"):
                raise ValueError(f"{entry.get('date')}: every mission needs a comment")

        total = sum(normalize_percentage(m["percentage"]) for m in missions)
        if abs(total - 1) > PERCENTAGE_SUM_TOLERANCE:
            raise ValueError(f"{entry.get('date')}: percentages sum to {total}, must sum to 1")

    return entries


def normalize_percentage(value):
    """Accepts either a 0-1 fraction (0.6) or a 0-100 percentage (60) and returns a 0-1 fraction."""
    value = float(value)
    return value / 100 if value > 1 else value


def submit_entry(page, entry):
    log(f"{entry['date']}: navigating to /daily-execution")
    page.goto(f"{ASA_BASE_URL}/daily-execution")

    log(f"{entry['date']}: setting date field")
    # #date is a readonly flatpickr-controlled input -- .fill() refuses to write to a readonly
    # field and just retries until its 30s timeout, so set the value directly instead.
    page.eval_on_selector("#date", "(el, val) => { el.value = val; }", entry["date"])

    for i, mission in enumerate(entry["missions"], start=1):
        log(f"{entry['date']}: filling mission slot {i} ({mission['code']}, {mission['percentage']})")
        page.select_option(f'select[name="missionCode{i}"]', mission["code"])
        page.fill(f'input[name="missionPercentage{i}"]', str(normalize_percentage(mission["percentage"])))
        page.fill(f'textarea[name="missionComment{i}"]', mission["comment"])

    log(f"{entry['date']}: submitting form")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{ASA_BASE_URL}/work-and-care-calendar", timeout=15000)
    log(f"{entry['date']}: submission confirmed")


def run(payload_path):
    log(f"loading payload from {payload_path}")
    entries = load_payload(payload_path)
    log(f"{len(entries)} entries loaded and validated")

    failures = []
    with sync_playwright() as p:
        browser, page = get_authenticated_page(p)

        for entry in entries:
            try:
                submit_entry(page, entry)
                print(f"OK   {entry['date']}")
            except Exception as e:
                print(f"FAIL {entry['date']}: {e}", file=sys.stderr)
                failures.append(entry["date"])

        browser.close()

    if failures:
        print(f"\n{len(failures)}/{len(entries)} entries failed: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit Asa daily-execution entries from a JSON payload file.")
    parser.add_argument(
        "payload",
        nargs="?",
        default=os.environ.get("ASA_PAYLOAD_FILE", "payload.json"),
        help="Path to the JSON payload file (default: payload.json, or $ASA_PAYLOAD_FILE)",
    )
    args = parser.parse_args()
    run(args.payload)

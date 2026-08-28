import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ASA_BASE_URL = os.environ["ASA_BASE_URL"]  # e.g. https://asa.hei.school
STATE_FILE = Path(os.environ.get("ASA_STATE_FILE", ".asa_state.json"))

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes to log in by hand


def get_authenticated_page(playwright):
    """Returns (browser, page) with an authenticated session against Asa.

    No password is ever handled by this script. If a saved session exists and is still valid, it's
    reused headlessly. Otherwise a real, visible browser window opens so you can log in through
    Casdoor by hand (however your org configured it -- password, SSO, 2FA, whatever), and the
    resulting session is saved to STATE_FILE for next time.
    """
    target_url = f"{ASA_BASE_URL}/daily-execution"

    if STATE_FILE.exists():
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(STATE_FILE))
        page = context.new_page()
        page.goto(target_url)
        if page.url.rstrip("/") == target_url.rstrip("/"):
            return browser, page
        browser.close()

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(target_url)

    print("A browser window opened -- log in through Casdoor, then this will continue automatically.")
    # Asa's OAuth2SuccessHandler always lands on "/" after login (it doesn't replay the originally
    # requested URL), so wait for any navigation back to the app's own origin, then go to the
    # actual target page ourselves.
    page.wait_for_url(lambda url: url.startswith(ASA_BASE_URL), timeout=LOGIN_TIMEOUT_MS)
    page.goto(target_url)

    context.storage_state(path=str(STATE_FILE))
    return browser, page

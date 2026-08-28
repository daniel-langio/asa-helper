import json
import re
import sys

from playwright.sync_api import sync_playwright

from asa_auth import get_authenticated_page

# The /daily-execution page's inline <script> contains, verbatim once rendered server-side:
#   const missions = /*[[${missions}]]*/ [];
# Thymeleaf's JS inlining replaces that comment with the real JSON array before the HTML is sent,
# so the array is just sitting in the page source as a literal -- no dedicated JSON API exists for it.
MISSIONS_RE = re.compile(r"const missions = (\[.*?\]);", re.DOTALL)


def fetch_missions(page):
    # Re-fetch the page's raw HTML (same authenticated session) rather than reading the live DOM,
    # since `missions` is a local const inside a function and isn't reachable as a global.
    html = page.evaluate("() => fetch(window.location.href).then(r => r.text())")
    match = MISSIONS_RE.search(html)
    if not match:
        raise RuntimeError(
            "could not find the `missions` array in /daily-execution's rendered HTML "
            "-- the page template may have changed"
        )
    return json.loads(match.group(1))


def run(output_path):
    with sync_playwright() as p:
        browser, page = get_authenticated_page(p)
        missions = fetch_missions(page)
        browser.close()

    with open(output_path, "w") as f:
        json.dump(missions, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(missions)} missions to {output_path}")
    for m in missions:
        print(f"  {m.get('code', '?'):<24} {m.get('title', '')}")


if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "missions.json"
    run(output_path)

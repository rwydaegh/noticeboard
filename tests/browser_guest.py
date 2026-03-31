"""Browser storage, account isolation and API docs checks against a running app."""

import json
import os
import secrets
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noticeboard.settings")
    import django

    django.setup()
    from django.contrib.auth import get_user_model

    username = "guest-qa-" + secrets.token_hex(4)
    password = secrets.token_urlsafe(20)
    user = get_user_model().objects.create_user(username=username, password=password)
    base = os.environ.get("NOTICEBOARD_URL", "http://127.0.0.1:8920")
    evidence = Path("private/qa/browser-storage")
    evidence.mkdir(parents=True, exist_ok=True)
    errors = []
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 950})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/?q=Service+Desk")
            page.locator(".notice-row").filter(has_text="Zajištění rozvojových").first.click()
            page.get_by_role("button", name="Save notice", exact=True).click()
            expect(page.get_by_role("dialog")).to_have_count(0)
            page.get_by_role("textbox", name="Notes", exact=True).fill("Browser-only note")
            page.get_by_label("Stage").select_option("reviewing")
            page.get_by_role("button", name="Save review", exact=True).click()
            expect(page.get_by_role("textbox", name="Notes", exact=True)).to_have_value("Browser-only note")
            page.reload()
            expect(page.get_by_role("textbox", name="Notes", exact=True)).to_have_value("Browser-only note")
            page.get_by_label("Question", exact=True).fill("Service Desk")
            page.get_by_role("button", name="Ask", exact=True).click()
            expect(page.locator("blockquote").first).to_be_visible()
            expect(page.get_by_label("Use AI")).to_have_count(0)
            checks.append("guest notes survive reload and source questions need no account")
            page.get_by_role("button", name="Close detail").click()
            page.get_by_role("button", name="Save search", exact=True).click()
            page.reload()
            expect(page.locator(".saved-query")).to_contain_text("Service Desk")
            page.get_by_role("navigation").get_by_role("button", name="Saved").click()
            expect(page.locator(".watch-entry")).to_contain_text("Browser-only note")
            with page.expect_download() as export:
                page.get_by_role("button", name="Export", exact=True).click()
            assert "Browser-only note" in Path(export.value.path()).read_text()
            with page.expect_download() as export:
                page.get_by_role("button", name="Calendar", exact=True).click()
            assert "20261103T100000Z" in Path(export.value.path()).read_text()
            checks.append("guest saved searches, review export and UTC calendar")
            page.get_by_role("navigation").get_by_role("button", name="Matches").click()
            page.get_by_label("Your work").fill("Python data software")
            page.get_by_role("button", name="Find matches", exact=True).click()
            expect(page.locator(".notice-row").first).to_be_visible(timeout=60000)
            page.reload()
            page.get_by_role("navigation").get_by_role("button", name="Matches").click()
            expect(page.get_by_label("Your work")).to_have_value("Python data software")
            checks.append("guest hybrid matches and profile persistence")
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("Username", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("dialog").get_by_role("button", name="Sign in", exact=True).click()
            expect(page.get_by_role("dialog")).to_have_count(0)
            page.get_by_role("navigation").get_by_role("button", name="Saved").click()
            expect(page.locator(".watch-entry")).to_have_count(0)
            page.get_by_role("button", name="Sign out", exact=True).click()
            page.get_by_role("navigation").get_by_role("button", name="Saved").click()
            expect(page.locator(".watch-entry")).to_contain_text("Browser-only note")
            checks.append("account and browser stores stay separate across login and logout")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(evidence / "mobile.png"))
            second = browser.new_page()
            second.goto(base)
            second.get_by_role("navigation").get_by_role("button", name="Saved").click()
            expect(second.locator(".watch-entry")).to_have_count(0)
            checks.append("separate browser context has no saved work")
            response = page.goto(base + "/api/docs")
            assert response.status == 200
            expect(page.locator(".swagger-ui .info .title")).to_contain_text("Noticeboard API")
            expect(page.locator(".opblock").first).to_be_visible()
            checks.append("API docs render their schema and endpoints")
            assert not errors, errors
            browser.close()
    finally:
        user.delete()
        (evidence / "results.json").write_text(json.dumps({"checks": checks, "errors": errors}, indent=2))
    print(f"Browser checks passed: {len(checks)}")


if __name__ == "__main__":
    main()

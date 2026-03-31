"""Run against a local installation: uv run --extra browser python tests/browser_smoke.py."""

import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noticeboard.settings")
import django

django.setup()
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

username = "qa-" + secrets.token_hex(5)
password = secrets.token_urlsafe(20)
user = get_user_model().objects.create_user(username=username, password=password)
evidence = Path("private/qa")
evidence.mkdir(parents=True, exist_ok=True)
errors = []
checks = []
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8920")
        expect(page.get_by_role("heading", name="Find a contract")).to_be_visible()
        page.get_by_role("textbox", name="Search notices").fill("Service Desk")
        page.get_by_role("button", name="Search", exact=True).click()
        page.locator(".notice-row").filter(has_text="Zajištění rozvojových").first.click()
        expect(page.get_by_role("complementary")).to_contain_text("666712-2026")
        checks.append("search and source detail")
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_label("Username", exact=True).fill(username)
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("dialog").get_by_role("button", name="Sign in", exact=True).click()
        expect(page.get_by_role("dialog")).not_to_be_visible()
        page.get_by_role("button", name="Save notice", exact=True).click()
        page.get_by_label("Notes").fill("QA review: check the source documents.")
        page.get_by_label("Stage").select_option("reviewing")
        page.get_by_role("button", name="Save review", exact=True).click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(evidence / "desktop-detail.png"))
        page.get_by_role("button", name="Close detail").click()
        page.get_by_role("navigation").get_by_role("button", name="Saved").click()
        expect(page.locator(".watch-entry")).to_contain_text("QA review")
        checks.append("session login, watchlist and review persistence")
        with page.expect_download() as download:
            page.get_by_role("link", name="Calendar").click()
        calendar = Path(download.value.path()).read_text()
        assert "BEGIN:VEVENT" in calendar and "20261103T100000Z" in calendar
        checks.append("calendar export retains exact UTC deadline")
        page.get_by_role("navigation").get_by_role("button", name="Browse").click()
        page.get_by_role("button", name="Save search", exact=True).click()
        expect(page.locator(".saved-query")).to_contain_text("Service Desk")
        checks.append("saved search")
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(evidence / "mobile-search.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator(".notice-row").first.click()
        expect(page.get_by_role("complementary")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(evidence / "mobile-detail.png"), full_page=True)
        page.keyboard.press("Escape")
        expect(page.get_by_role("complementary")).not_to_be_visible()
        checks.append("mobile layout and Escape navigation")
        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible()
        checks.append("logout")
        browser.close()
    assert not errors, errors
finally:
    user.delete()
    (evidence / "browser-results.json").write_text(
        json.dumps({"checks": checks, "page_errors": errors}, indent=2)
    )
print(f"Browser checks passed: {len(checks)}")

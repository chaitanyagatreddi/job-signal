"""Quick test: can Browserbase reach LinkedIn at all?"""
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from config import BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, LINKEDIN_LI_AT
import time

bb = Browserbase(api_key=BROWSERBASE_API_KEY)
session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)
cdp_url = f"wss://connect.browserbase.com?apiKey={BROWSERBASE_API_KEY}&sessionId={session.id}"

print(f"Session: {session.id}")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    # Try just the homepage first, no cookie
    print("Trying linkedin.com (no cookie)...")
    try:
        page.goto("https://www.linkedin.com/", timeout=15000)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
    except Exception as e:
        print(f"  Error: {e}")

    # Try Google as control
    print("\nTrying google.com (control)...")
    try:
        page.goto("https://www.google.com/", timeout=15000)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
    except Exception as e:
        print(f"  Error: {e}")

    browser.close()

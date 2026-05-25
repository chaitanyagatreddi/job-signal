"""Test LinkedIn with Browserbase proxy + persistent context."""
import os
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import time

load_dotenv()

BB_KEY = os.getenv("BROWSERBASE_API_KEY")
BB_PROJECT = os.getenv("BROWSERBASE_PROJECT_ID")
LI_AT = os.getenv("LINKEDIN_LI_AT")
JSESSIONID = os.getenv("LINKEDIN_JSESSIONID")

bb = Browserbase(api_key=BB_KEY)

# Create session with proxy enabled (residential IP)
session = bb.sessions.create(
    project_id=BB_PROJECT,
    proxies=True,
)
cdp_url = f"wss://connect.browserbase.com?apiKey={BB_KEY}&sessionId={session.id}"
print(f"Session: {session.id} (proxy enabled)")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    # Set cookies before navigation
    context.add_cookies([
        {
            "name": "li_at",
            "value": LI_AT,
            "domain": ".linkedin.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "JSESSIONID",
            "value": '"' + JSESSIONID + '"',
            "domain": ".www.linkedin.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        },
    ])

    print("Navigating to LinkedIn feed (with proxy)...")
    try:
        page.goto("https://www.linkedin.com/feed/", timeout=30000)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
    except Exception as e:
        print(f"  Error: {e}")

        # Fallback: try just the homepage and reload
        print("\nTrying homepage then redirect...")
        page.goto("https://www.linkedin.com/", timeout=15000)
        time.sleep(3)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")

    browser.close()

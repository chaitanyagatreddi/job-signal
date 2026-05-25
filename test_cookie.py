"""Test LinkedIn cookie injection with li_at + JSESSIONID."""
import os
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import time

load_dotenv()

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
LINKEDIN_JSESSIONID = os.getenv("LINKEDIN_JSESSIONID")

bb = Browserbase(api_key=BROWSERBASE_API_KEY)
session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)
cdp_url = f"wss://connect.browserbase.com?apiKey={BROWSERBASE_API_KEY}&sessionId={session.id}"

print(f"Session: {session.id}")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    # Load LinkedIn homepage first
    page.goto("https://www.linkedin.com/", timeout=15000)
    time.sleep(2)

    # Inject both cookies
    context.add_cookies([
        {
            "name": "li_at",
            "value": LINKEDIN_LI_AT,
            "domain": ".linkedin.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "JSESSIONID",
            "value": '"' + LINKEDIN_JSESSIONID + '"',
            "domain": ".www.linkedin.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        },
    ])
    print("Both cookies injected")

    # Navigate to feed
    print("Navigating to /feed/...")
    try:
        page.goto("https://www.linkedin.com/feed/", timeout=20000)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
    except Exception as e:
        print(f"  Error: {e}")

    browser.close()

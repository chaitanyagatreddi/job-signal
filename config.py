"""
JobSignal Configuration & Guardrails
All rate limits, safety caps, and credential validation.
"""

import os
import sys
import json
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Rate Limits ---
DAILY_LINKEDIN_CAP = 70          # Hard cap per day
PAUSE_THRESHOLD = 65             # Auto-pause at this count
HITS_PER_SCHEDULED_RUN = 50      # Target hits per scheduled run
COOLDOWN_MIN = 2                 # Min seconds between actions
COOLDOWN_MAX = 5                 # Max seconds between actions
WARMUP_DAILY_START = 20          # New accounts start here
WARMUP_INCREMENT_DAYS = 14       # Days to reach full cap

# --- Paths ---
DATA_DIR = Path(__file__).parent / "data"
HITS_FILE = DATA_DIR / "daily_hits.json"

# --- Credentials ---
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")


def _prompt_and_save(key: str, prompt_msg: str, help_text: str = "") -> str:
    """Prompt user to paste a credential and save it to .env."""
    print(f"\n🔑 {prompt_msg}")
    if help_text:
        print(f"   How to find it: {help_text}")
    value = input("   Paste here → ").strip()
    if not value:
        print(f"   ❌ No value entered for {key}. Exiting.")
        sys.exit(1)

    # Save to .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        content = env_path.read_text()
        if f"{key}=" in content:
            # Replace existing empty value
            lines = content.split("\n")
            lines = [f"{key}={value}" if line.startswith(f"{key}=") else line for line in lines]
            env_path.write_text("\n".join(lines))
        else:
            env_path.write_text(content.rstrip() + f"\n{key}={value}\n")
    else:
        env_path.write_text(f"{key}={value}\n")

    os.environ[key] = value
    print(f"   ✅ {key} saved to .env")
    return value


def validate_credentials():
    """Check all required credentials. Prompt user to paste missing ones interactively."""
    global LINKEDIN_LI_AT, BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, OPENAI_API_KEY, APIFY_API_TOKEN

    if not LINKEDIN_LI_AT:
        print("\n" + "=" * 60)
        print("📋 WHAT IS A LINKEDIN COOKIE (li_at)?")
        print("=" * 60)
        print("""
The li_at cookie is how LinkedIn knows you're logged in.
JobSignal uses it to search LinkedIn posts on your behalf.

⚠️  USE A BURNER ACCOUNT — not your real LinkedIn.
    Automated scraping can get accounts flagged.

HOW TO FIND IT:
  1. Log into LinkedIn in your browser (Chrome/Firefox/Edge)
  2. Open DevTools:
     - Chrome/Edge: Cmd+Option+I (Mac) or F12 (Windows)
     - Firefox:     Cmd+Option+I (Mac) or F12 (Windows)
  3. Go to the tab:
     - Chrome/Edge: Application → Cookies → linkedin.com
     - Firefox:     Storage → Cookies → linkedin.com
  4. Find the row named 'li_at'
  5. Copy the Value (starts with 'AQ...' or 'v=1&...')

The cookie expires after ~1 year. If scraping stops working,
get a fresh one by repeating these steps.
""")
        print("=" * 60)
        LINKEDIN_LI_AT = _prompt_and_save(
            "LINKEDIN_LI_AT",
            "Paste your LinkedIn li_at cookie below.",
            ""
        )

    if not BROWSERBASE_API_KEY:
        BROWSERBASE_API_KEY = _prompt_and_save(
            "BROWSERBASE_API_KEY",
            "Browserbase API key required.",
            "browserbase.com → Dashboard → Quick access → API key"
        )

    if not BROWSERBASE_PROJECT_ID:
        BROWSERBASE_PROJECT_ID = _prompt_and_save(
            "BROWSERBASE_PROJECT_ID",
            "Browserbase Project ID required.",
            "browserbase.com → Dashboard → URL contains the project ID after /orgs/..."
        )

    if not OPENAI_API_KEY:
        OPENAI_API_KEY = _prompt_and_save(
            "OPENAI_API_KEY",
            "OpenAI API key required.",
            "platform.openai.com → API keys → Create new secret key"
        )

    # Apify is optional — prompt but don't block
    if not APIFY_API_TOKEN:
        print("\n⚠️  No Apify API token set. You'll be prompted to add one if LinkedIn cap is hit.")
        add_now = input("   Add Apify token now? (y/n) → ").strip().lower()
        if add_now == "y":
            APIFY_API_TOKEN = _prompt_and_save(
                "APIFY_API_TOKEN",
                "Apify API token.",
                "apify.com → Settings → Integrations → API token"
            )

    print("\n✅ All credentials validated.")


def get_today_hits() -> int:
    """Get the number of LinkedIn hits used today."""
    if not HITS_FILE.exists():
        return 0

    data = json.loads(HITS_FILE.read_text())
    today = date.today().isoformat()

    return data.get(today, 0)


def record_hit(count: int = 1):
    """Record LinkedIn hits. Returns (new_total, should_pause, should_stop)."""
    today = date.today().isoformat()

    if HITS_FILE.exists():
        data = json.loads(HITS_FILE.read_text())
    else:
        data = {}

    current = data.get(today, 0)
    new_total = current + count
    data[today] = new_total

    HITS_FILE.write_text(json.dumps(data, indent=2))

    should_pause = new_total >= PAUSE_THRESHOLD
    should_stop = new_total >= DAILY_LINKEDIN_CAP

    return new_total, should_pause, should_stop


def check_can_scrape() :
    """Check if we can scrape. Returns (can_scrape, reason)."""
    hits = get_today_hits()

    if hits >= DAILY_LINKEDIN_CAP:
        msg = f"🛑 Daily cap reached ({hits}/{DAILY_LINKEDIN_CAP})."
        if APIFY_API_TOKEN:
            msg += " Switching to Apify fallback."
        else:
            msg += " Set APIFY_API_TOKEN in .env to use Apify fallback."
        return False, msg

    if hits >= PAUSE_THRESHOLD:
        remaining = DAILY_LINKEDIN_CAP - hits
        msg = f"⚠️  Approaching daily cap ({hits}/{DAILY_LINKEDIN_CAP}). {remaining} hits remaining. Proceed carefully."
        return True, msg

    return True, f"✅ {hits}/{DAILY_LINKEDIN_CAP} hits used today."


def get_cooldown() -> float:
    """Get randomized cooldown between actions."""
    import random
    return random.uniform(COOLDOWN_MIN, COOLDOWN_MAX)


if __name__ == "__main__":
    validate_credentials()
    can_scrape, msg = check_can_scrape()
    print(msg)

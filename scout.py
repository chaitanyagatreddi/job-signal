"""
Agent 1: Scout
Searches LinkedIn posts for hiring signals using Apify's LinkedIn Post Search actor.
No cookies or LinkedIn account needed.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

from config import (
    APIFY_API_TOKEN,
    check_can_scrape,
    record_hit,
    validate_credentials,
    DATA_DIR,
)

# --- Search queries that signal real hiring intent ---
HIRING_QUERIES = [
    "we're hiring head of Bangalore",
    "looking for growth lead startup India",
    "join our team AI startup Bangalore",
    "open role series A seed India",
    "hiring machine learning engineer Bangalore",
    "we're hiring remote India",
]

OUTPUT_FILE = DATA_DIR / "raw_signals.json"
APIFY_ACTOR = "harvestapi~linkedin-post-search"
APIFY_BASE = "https://api.apify.com/v2"


def search_linkedin_posts(query, max_posts=10):
    """Search LinkedIn posts via Apify. Returns list of post dicts."""
    can_scrape, msg = check_can_scrape()
    if not can_scrape:
        print(msg)
        return []

    print(f"🔍 Searching: {query}")

    url = f"{APIFY_BASE}/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"
    params = {"token": APIFY_API_TOKEN}
    payload = {
        "searchQueries": [query],
        "maxPosts": max_posts,
        "sortBy": "date",
        "postedLimit": "week",
    }

    try:
        resp = requests.post(url, json=payload, params=params, timeout=180)

        if resp.status_code == 402:
            print("   ❌ Apify free tier limit reached.")
            return []

        if resp.status_code not in (200, 201):
            print(f"   ❌ Apify error: {resp.status_code} - {resp.text[:200]}")
            return []

        results = resp.json()

        # Record hits based on results count
        hit_count = len(results) if results else 1
        total, should_pause, should_stop = record_hit(hit_count)
        if should_stop:
            print(f"   🛑 Daily cap reached ({total}/70). Stopping.")
            return results
        if should_pause:
            print(f"   ⚠️  Approaching cap ({total}/70).")

        print(f"   ✅ Found {len(results)} posts")
        return results

    except requests.Timeout:
        print("   ❌ Apify request timed out (3 min). Try later.")
        return []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


def normalize_post(raw):
    """Normalize Apify output to our standard signal format."""
    author = raw.get("author", {})
    posted_at = raw.get("postedAt", {})
    stats = raw.get("stats", {})

    return {
        "author": author.get("name", "Unknown") if isinstance(author, dict) else str(author),
        "author_title": author.get("info", "") if isinstance(author, dict) else "",
        "author_profile_url": author.get("linkedinUrl", "") if isinstance(author, dict) else "",
        "post_text": raw.get("content", ""),
        "likes": stats.get("numLikes", 0) if isinstance(stats, dict) else 0,
        "comments": stats.get("numComments", 0) if isinstance(stats, dict) else 0,
        "reposts": stats.get("numShares", 0) if isinstance(stats, dict) else 0,
        "post_url": raw.get("linkedinUrl", ""),
        "posted_at": posted_at.get("date", "") if isinstance(posted_at, dict) else str(posted_at),
        "posted_ago": posted_at.get("postedAgoText", "") if isinstance(posted_at, dict) else "",
        "scraped_at": datetime.now().isoformat(),
        "source": "linkedin_apify",
    }


def save_signals(posts):
    """Append posts to raw signals file, deduplicated."""
    existing = []
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text())

    existing_urls = {p.get("post_url", "") for p in existing if p.get("post_url")}
    new_posts = [p for p in posts if p.get("post_url", "") not in existing_urls]

    existing.extend(new_posts)
    OUTPUT_FILE.write_text(json.dumps(existing, indent=2))
    print(f"\n💾 Saved {len(new_posts)} new signals ({len(existing)} total)")


def run():
    """Run the Scout agent."""
    validate_credentials()

    can_scrape, msg = check_can_scrape()
    print(msg)
    if not can_scrape:
        return

    print("\n🕵️ Scout Agent starting...")
    print(f"   Running {len(HIRING_QUERIES)} search queries via Apify\n")

    all_posts = []

    for query in HIRING_QUERIES:
        can_scrape, msg = check_can_scrape()
        if not can_scrape:
            print(msg)
            break

        raw_results = search_linkedin_posts(query)
        normalized = [normalize_post(r) for r in raw_results]
        normalized = [p for p in normalized if p["post_text"]]
        all_posts.extend(normalized)

        time.sleep(2)

    if all_posts:
        save_signals(all_posts)

    print(f"\n🏁 Scout complete. {len(all_posts)} posts found.")


if __name__ == "__main__":
    run()

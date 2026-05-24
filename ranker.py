"""
Agent 2: Ranker
Scores and ranks hiring signals using Twitter/X algorithm-inspired signals.

Adapted from twitter/the-algorithm (open source):
- Engagement velocity (Twitter: first 30-min gate) → 30%
- Author authority (Twitter: 50x multiplier) → 35%
- Recency (Twitter: 22x multiplier) → 25%
- Reply ratio (Twitter: replies weighted 27x over likes) → 10%
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR

INPUT_FILE = DATA_DIR / "raw_signals.json"
OUTPUT_FILE = DATA_DIR / "ranked_signals.json"

# --- Authority title signals ---
# Twitter uses author authority as a 50x multiplier.
# We adapt: founder/CTO/CEO = highest, VP/Head = high, recruiter = medium
TITLE_AUTHORITY = {
    "founder": 1.0,
    "co-founder": 1.0,
    "ceo": 1.0,
    "cto": 0.95,
    "coo": 0.9,
    "cpo": 0.9,
    "vp": 0.8,
    "vice president": 0.8,
    "head of": 0.75,
    "director": 0.7,
    "partner": 0.7,
    "general manager": 0.65,
    "hiring manager": 0.6,
    "recruiter": 0.4,
    "talent": 0.4,
    "hr": 0.35,
}

# --- Hiring intent keywords ---
# Posts with strong hiring language get a bonus
STRONG_INTENT = [
    "we're hiring", "we are hiring", "i'm hiring", "im hiring",
    "looking for", "open role", "join our team", "join us",
    "come work with", "building a team", "growing the team",
    "head of", "looking to hire",
]

WEAK_INTENT = [
    "hiring", "role", "position", "opportunity", "apply",
    "job", "career", "openings",
]

# --- Location signals ---
# Posts mentioning target locations get a bonus
TARGET_LOCATIONS = [
    "bangalore", "bengaluru", "india", "remote",
    "hyderabad", "mumbai", "delhi", "pune",
]


def score_recency(post):
    """
    Recency score (25% weight).
    Twitter: 22x multiplier for fresh content.
    Posts < 24h = 1.0, 1-3 days = 0.8, 3-7 days = 0.5, 7+ days = 0.2
    """
    posted_at = post.get("posted_at", "")
    if not posted_at:
        return 0.3  # Unknown date, assume moderate

    try:
        if isinstance(posted_at, str):
            # Try ISO format
            post_time = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        else:
            return 0.3

        now = datetime.now(timezone.utc)
        hours_ago = (now - post_time).total_seconds() / 3600

        if hours_ago < 24:
            return 1.0
        elif hours_ago < 72:
            return 0.8
        elif hours_ago < 168:  # 7 days
            return 0.5
        else:
            return 0.2

    except (ValueError, TypeError):
        # Try parsing "posted_ago" field
        posted_ago = post.get("posted_ago", "").lower()
        if "hour" in posted_ago or "minute" in posted_ago:
            return 1.0
        elif "1 day" in posted_ago or "2 day" in posted_ago:
            return 0.8
        elif "day" in posted_ago:
            return 0.5
        elif "week" in posted_ago:
            return 0.2
        return 0.3


def score_author_authority(post):
    """
    Author authority score (35% weight).
    Twitter: 50x multiplier for authoritative accounts.
    Combines title signal + follower count (log-scaled).
    """
    title = post.get("author_title", "").lower()

    # Title signal (0-1)
    title_score = 0.2  # Default for unknown titles
    for keyword, score in TITLE_AUTHORITY.items():
        if keyword in title:
            title_score = score
            break

    # Follower signal (log-scaled, 0-1)
    followers = post.get("follower_count", 0)
    if isinstance(followers, str):
        followers = int(followers.replace(",", "").replace("+", "")) if followers.isdigit() else 0

    if followers > 0:
        # log10(1000) = 3, log10(100000) = 5, log10(1000000) = 6
        follower_score = min(1.0, math.log10(max(followers, 1)) / 6)
    else:
        follower_score = 0.1  # Unknown followers

    # Weighted: 60% title, 40% followers
    return (title_score * 0.6) + (follower_score * 0.4)


def score_engagement_velocity(post):
    """
    Engagement velocity score (30% weight).
    Twitter: first 30-min engagement velocity is the #1 viral signal.
    We measure total engagement relative to post age.
    """
    likes = _to_int(post.get("likes", 0))
    comments = _to_int(post.get("comments", 0))
    reposts = _to_int(post.get("reposts", 0))

    # Twitter weights: replies 27x, likes 1x, retweets 1x
    # We adapt: comments are strongest signal for hiring posts
    weighted_engagement = (comments * 5.0) + (likes * 1.0) + (reposts * 2.0)

    if weighted_engagement == 0:
        return 0.05

    # Estimate hours since posted
    posted_ago = post.get("posted_ago", "").lower()
    hours = _estimate_hours(posted_ago, post.get("posted_at", ""))

    if hours <= 0:
        hours = 24  # Default assumption

    # Velocity = engagement per hour
    velocity = weighted_engagement / hours

    # Normalize: 0-1 scale
    # velocity of 1/hr = decent, 5/hr = good, 20/hr = viral
    return min(1.0, velocity / 20.0)


def score_reply_ratio(post):
    """
    Reply ratio score (10% weight).
    Twitter: replies weighted 27x over likes — conversation = quality.
    High comment-to-like ratio on a hiring post = real engagement.
    """
    likes = _to_int(post.get("likes", 0))
    comments = _to_int(post.get("comments", 0))

    if likes == 0 and comments == 0:
        return 0.0

    if likes == 0:
        return 1.0  # All comments, no likes = very conversational

    ratio = comments / (likes + comments)

    # Ratio > 0.3 is very conversational (hiring posts where people say "interested!")
    return min(1.0, ratio * 2.5)


def score_hiring_intent(post):
    """
    Bonus: hiring intent strength (added to final score).
    Not from Twitter — our domain-specific signal.
    """
    text = post.get("post_text", "").lower()

    for phrase in STRONG_INTENT:
        if phrase in text:
            return 0.15  # Strong bonus

    for word in WEAK_INTENT:
        if word in text:
            return 0.05  # Weak bonus

    return -0.1  # No hiring signal = penalty


def score_location(post):
    """
    Bonus: location match.
    Posts mentioning target locations (Bangalore, India, remote) get a boost.
    """
    text = (post.get("post_text", "") + " " + post.get("author_title", "")).lower()

    for loc in TARGET_LOCATIONS:
        if loc in text:
            return 0.10  # Location match bonus

    return 0.0  # No penalty, just no bonus


def rank_post(post):
    """
    Calculate final ranking score for a post.
    Returns score 0-1 (higher = stronger hiring signal).
    """
    recency = score_recency(post) * 0.25
    authority = score_author_authority(post) * 0.35
    velocity = score_engagement_velocity(post) * 0.30
    reply_ratio = score_reply_ratio(post) * 0.10
    intent = score_hiring_intent(post)
    location = score_location(post)

    score = recency + authority + velocity + reply_ratio + intent + location

    # Clamp to 0-1
    return max(0.0, min(1.0, score))


def rank_all(posts):
    """Rank all posts and return sorted list with scores."""
    scored = []
    for post in posts:
        score = rank_post(post)
        post["rank_score"] = round(score, 4)
        post["rank_breakdown"] = {
            "recency": round(score_recency(post), 3),
            "authority": round(score_author_authority(post), 3),
            "velocity": round(score_engagement_velocity(post), 3),
            "reply_ratio": round(score_reply_ratio(post), 3),
            "intent": round(score_hiring_intent(post), 3),
            "location": round(score_location(post), 3),
        }
        scored.append(post)

    # Sort descending by score
    scored.sort(key=lambda x: x["rank_score"], reverse=True)
    return scored


def _to_int(val):
    """Convert engagement value to int."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.replace(",", "").replace("+", "").strip()
        try:
            return int(val)
        except ValueError:
            return 0
    return 0


def _estimate_hours(posted_ago, posted_at):
    """Estimate hours since posting from text or timestamp."""
    if posted_ago:
        posted_ago = posted_ago.lower()
        if "minute" in posted_ago:
            return 0.5
        elif "hour" in posted_ago:
            parts = posted_ago.split()
            if parts and parts[0].isdigit():
                return int(parts[0])
            return 1
        elif "day" in posted_ago:
            parts = posted_ago.split()
            if parts and parts[0].isdigit():
                return int(parts[0]) * 24
            return 24
        elif "week" in posted_ago:
            return 168

    if posted_at:
        try:
            post_time = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return max(1, (now - post_time).total_seconds() / 3600)
        except (ValueError, TypeError):
            pass

    return 24  # Default


def run():
    """Run the Ranker agent."""
    if not INPUT_FILE.exists():
        print("❌ No raw signals found. Run scout.py first.")
        return

    posts = json.loads(INPUT_FILE.read_text())
    print(f"📊 Ranker Agent starting...")
    print(f"   {len(posts)} raw signals loaded\n")

    ranked = rank_all(posts)

    OUTPUT_FILE.write_text(json.dumps(ranked, indent=2))
    print(f"💾 Saved {len(ranked)} ranked signals to {OUTPUT_FILE.name}\n")

    # Show top 10
    print("🏆 TOP 10 HIRING SIGNALS:\n")
    print(f"{'#':<3} {'Score':<7} {'Author':<25} {'Title':<35} {'Posted':<15}")
    print("-" * 90)

    for i, post in enumerate(ranked[:10], 1):
        author = post["author"][:24]
        title = post["author_title"][:34]
        posted = post.get("posted_ago", "")[:14]
        score = post["rank_score"]
        print(f"{i:<3} {score:<7.3f} {author:<25} {title:<35} {posted:<15}")

    print(f"\n   Breakdown of #1:")
    if ranked:
        bd = ranked[0]["rank_breakdown"]
        print(f"   Recency: {bd['recency']:.2f} | Authority: {bd['authority']:.2f} | "
              f"Velocity: {bd['velocity']:.2f} | Reply ratio: {bd['reply_ratio']:.2f} | "
              f"Intent: {bd['intent']:.2f}")
        print(f"\n   Post: {ranked[0]['post_text'][:150]}...")


if __name__ == "__main__":
    run()

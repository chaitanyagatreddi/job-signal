# JobSignal

Find real hiring intent from people who are actually hiring — not job boards full of ghost listings.

JobSignal scrapes LinkedIn posts and Twitter from founders, CTOs, and recruiters in the last 2 weeks, ranks them using engagement signals inspired by Twitter's open-source recommendation engine, scores your fit using the STAR framework, and tells you honestly where you stand.

## The Problem

Most job listings are fake or stale. LinkedIn's job board is noise. But when a founder posts "we're hiring a Head of Growth" on their personal profile at 11pm — that's real. JobSignal finds those signals.

## Architecture

```
+----------------------------------------------------------+
|                     RUFLO SWARM                          |
|                   (Orchestrator)                         |
|                                                          |
|  +------------+  +------------+  +------------+          |
|  |  Agent 1   |  |  Agent 2   |  |  Agent 3   |   ...   |
|  |  Burner A  |  |  Burner B  |  |  Burner C  |          |
|  +-----+------+  +-----+------+  +-----+------+          |
|        |               |               |                 |
+--------|---------------|---------------|----------------+
         |               |               |
         v               v               v
+----------------------------------------------------------+
|                   BROWSERBASE                            |
|              (Cloud Browser Sessions)                    |
|                                                          |
|  Each agent has its own Browserbase Context              |
|  (persisted login session via li_at cookie)              |
|                                                          |
|  Searches:                                               |
|  - "we're hiring" + role keywords                        |
|  - "looking for" + role keywords                         |
|  - "join our team" + industry                            |
|  - Founder/CTO profile post feeds                        |
|                                                          |
|  Cap: 80 searches/agent/day                              |
|  On cap hit: STOP + alert user + offer Apify fallback    |
+----------------------------+-----------------------------+
                             |
                             v
+----------------------------------------------------------+
|                   RAW SIGNAL STORE                        |
|                     (JSON/DB)                            |
|                                                          |
|  Post text, author name, title, company,                 |
|  date posted, likes, comments, reposts,                  |
|  post URL, author profile URL                            |
+----------------------------+-----------------------------+
                             |
                             v
+----------------------------------------------------------+
|              RANKING ENGINE (Layer 2)                     |
|     Twitter Recommendation Signals (Adapted)             |
|                                                          |
|  Score = weighted sum of:                                |
|                                                          |
|  Recency (40%)                                           |
|    - Posts < 3 days = 1.0                                |
|    - Posts 3-7 days = 0.7                                |
|    - Posts 7-14 days = 0.4                               |
|                                                          |
|  Author Authority (35%)                                  |
|    - Follower count (log-scaled)                         |
|    - Title signal (founder/CTO/VP > recruiter > other)   |
|    - Company stage (startup > enterprise for urgency)    |
|                                                          |
|  Engagement Velocity (25%)                               |
|    - Likes + comments per hour since posting             |
|    - High velocity = post is gaining traction now        |
+----------------------------+-----------------------------+
                             |
                             v
+----------------------------------------------------------+
|              LLM FILTER (Layer 3)                        |
|                  GPT-4o-mini                             |
|                                                          |
|  Input: ranked posts + user profile                      |
|  Output: top 10 leads with relevance score               |
|                                                          |
|  Filters for:                                            |
|  - Role match (Head of Growth, GTM, AI PM)               |
|  - Industry match (AI, SaaS, devtools, security)         |
|  - Seniority match                                       |
|  - Location/remote compatibility                         |
+----------------------------+-----------------------------+
                             |
                             v
+----------------------------------------------------------+
|            STAR FRAMEWORK ANALYZER (Layer 4)              |
|                                                          |
|  When user selects a lead and pastes the JD:             |
|                                                          |
|  1. PARSE JD                                             |
|     Break each requirement into STAR components:         |
|     - Situation: what context is needed?                 |
|     - Task: what was the goal?                           |
|     - Action: what did YOU specifically do?              |
|     - Result: what measurable outcome?                   |
|                                                          |
|  2. MATCH RESUME                                         |
|     For each JD requirement, check resume for evidence:  |
|     - Which STAR components are covered?                 |
|     - Which are missing?                                 |
|     - Score: 0-10 per requirement                        |
|                                                          |
|  3. ASK FOR PROOF                                        |
|     Request portfolio links, case studies, GitHub repos   |
|     that fill the gaps                                   |
|                                                          |
|  4. TRANSPARENT SCORING                                  |
|     Show exactly how each point is scored:               |
|                                                          |
|     "Cross-functional leadership: 7/10                   |
|      S: Writesonic, $1M ARR, 12-person team [x]         |
|      T: Scale to market-defining position [x]            |
|      A: Hand-picked and trained every hire [x]           |
|      R: $18M ARR — but no retention metric shown [-]     |
|      Add: churn rate or NRR to reach 9/10"               |
|                                                          |
|  5. FILL GAPS + RESCORE                                  |
|     User adds missing info -> score updates live         |
|     Show before/after comparison                         |
+----------------------------------------------------------+


## Safety & Rate Limiting

| Rule                        | Value                                    |
|-----------------------------|------------------------------------------|
| Max searches per agent/day  | 70                                       |
| Cool-down between actions   | 2-5 seconds (randomized, human-like)     |
| New account warm-up         | Start at 20/day, increment over 2 weeks  |
| On cap exhaustion           | Agent stops, prompts user to use Apify   |
| Account type                | User's LinkedIn (burner recommended)      |
| Setup: Basic (free)         | LinkedIn account + free Apify account      |
| Setup: Power (BYO keys)     | OpenAI + Browserbase + Apify API keys      |
| Browserbase Context         | One per burner, persists login session    |
| Scheduler                   | User sets run frequency (e.g., 3 days/wk) |
| Scheduler hits/run          | ~50 LinkedIn hits per scheduled run        |
| Cumulative safety threshold | Auto-pause at 65 hits, protect account     |
| Resume                      | After cooldown period, scheduler resumes   |


## Execution Plan

### Phase 0: Setup (Day 1)
- [ ] Fix Browserbase API key
- [ ] Create burner LinkedIn account(s) — start with 1
- [ ] Set up Browserbase Context with burner login (one manual login, saved)
- [ ] Create project repo, install dependencies

### Phase 1: Scrape LinkedIn Posts (Days 2-3)
- [ ] Build Python scraper using Browserbase MCP
- [ ] Search LinkedIn posts by hiring keywords (last 14 days)
- [ ] Extract: post text, author, title, company, date, engagement metrics, URL
- [ ] Output raw JSON to local file
- [ ] Implement 80/day cap + alert logic
- [ ] Test with 1 agent, 1 keyword, 10 results

### Phase 2: Ranking Engine (Days 4-5)
- [ ] Study twitter/the-algorithm repo for ranking signal logic
- [ ] Build scoring module: recency (40%) + author authority (35%) + engagement velocity (25%)
- [ ] Rank raw posts, output sorted JSON
- [ ] Validate: do the top-ranked posts feel like real hiring signals?

### Phase 3: LLM Filter (Days 5-6)
- [ ] Build GPT-4o-mini filter layer
- [ ] Input: ranked posts + user profile YAML
- [ ] Output: top 10 leads with relevance score + reasoning
- [ ] Test against your own profile — do the leads make sense?

### Phase 4: STAR Analyzer (Days 7-9)
- [ ] Build JD parser — break requirements into STAR components
- [ ] Build resume matcher — check coverage per requirement
- [ ] Build scoring display — transparent 0-10 per requirement
- [ ] Build gap identifier — what's missing, what to add
- [ ] Build rescore flow — user adds info, score updates
- [ ] Portfolio/proof-of-work input — accept links, case study references

### Phase 5: Multi-Agent Swarm (Days 10-12)
- [ ] Set up Ruflo swarm with 3-5 agents
- [ ] Each agent gets its own Browserbase Context + burner account
- [ ] Distribute keyword searches across agents
- [ ] Aggregate results to central store
- [ ] Implement Apify fallback on cap exhaustion

### Phase 6: Twitter / X Layer (Days 13-15)
- [ ] Add X/Twitter post scraping (evaluate: X API vs Grok API vs scraper)
- [ ] Apply same ranking + filter pipeline
- [ ] Merge LinkedIn + Twitter signals into unified feed

### Phase 7: Polish & Portfolio (Days 16-18)
- [ ] Build simple CLI or web UI to view results
- [ ] Write up as AI PM case study
- [ ] Document architecture decisions and tradeoffs
- [ ] Push to GitHub as portfolio piece


## Tech Stack

| Component          | Tool                                          |
|--------------------|-----------------------------------------------|
| Orchestration      | Ruflo (multi-agent swarm)                     |
| Browser Automation | Browserbase (cloud browser sessions)          |
| Fallback Scraping  | Apify (LinkedIn Post Search Scraper actor)    |
| Ranking Logic      | Python (inspired by twitter/the-algorithm)    |
| LLM Filter         | OpenAI GPT-4o-mini                            |
| STAR Analyzer      | OpenAI GPT-4o-mini                            |
| Runtime            | Python 3.11+                                  |
| Data Store         | JSON files (MVP) -> SQLite (v2)               |
| Hosting            | Render (free plan)                             |


## Inspired By

- [twitter/the-algorithm](https://github.com/twitter/the-algorithm) — ranking signal design
- [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) — engagement velocity scoring
- [STAR Method](https://nationalcareers.service.gov.uk/careers-advice/interview-advice/the-star-method) — structured skill assessment
- [AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk) — prior art in job application automation (core open-sourced, plugins removed)


## Quick Start

```bash
# Clone
git clone https://github.com/chaitanyagatreddi/job-signal.git
cd job-signal

# Install dependencies
pip install -r requirements.txt

# Run setup — prompts for API keys on first run
python3 config.py
```

### What you need

| Key | Where to get it | Cost |
|-----|----------------|------|
| Apify API token | [apify.com](https://apify.com) → Settings → Integrations | Free tier available |
| OpenAI API key | [platform.openai.com](https://platform.openai.com) → API keys | Pay per use |

Optional (for power users):
| Key | Where to get it |
|-----|----------------|
| Browserbase API key | [browserbase.com](https://browserbase.com) → Dashboard → API key |

### Run the pipeline

```bash
# Step 1: Scout — scrape LinkedIn hiring posts
python3 scout.py

# Step 2: Rank — score posts using X algorithm signals
python3 ranker.py

# Step 3: Parse your resume (paste or save to data/resume.txt)
python3 parser.py

# Step 4: STAR analysis — paste a JD (or save to data/jd.txt)
python3 star.py
```

### Pipeline flow

```
scout.py → data/raw_signals.json
ranker.py → data/ranked_signals.json
parser.py → data/parsed_profile.json
star.py → data/star_analysis.json
```

Each agent reads the previous agent's output. Run them in order.


## Why This Exists

Job boards are broken. LinkedIn shows ghost listings. Most "AI resume tools" just say "great match!" without showing their work.

JobSignal does three things differently:
1. Finds real hiring intent from social posts, not stale job listings
2. Ranks signals by urgency and credibility, not keyword matching
3. Tells you honestly that you're 7/10 — and shows you exactly what gets you to 9/10


## License

MIT

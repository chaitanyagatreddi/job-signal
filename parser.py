"""
Agent 3: Parser
Parses user's resume into structured profile data using GPT-4o-mini.
Extracts: skills, experience, achievements, industries, seniority level.
Output feeds into the STAR Agent for JD matching.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY, validate_credentials, DATA_DIR

PROFILE_FILE = DATA_DIR / "parsed_profile.json"

SYSTEM_PROMPT = """You are a resume parser. Extract structured data from the resume text provided.

Return a JSON object with these fields:
{
  "name": "Full name",
  "current_title": "Most recent job title",
  "current_company": "Most recent company",
  "seniority": "one of: entry, mid, senior, lead, director, vp, c-level",
  "years_experience": number,
  "industries": ["list of industries worked in"],
  "skills": {
    "technical": ["list of technical/hard skills"],
    "leadership": ["list of leadership/management skills"],
    "domain": ["list of domain expertise areas"]
  },
  "achievements": [
    {
      "description": "What was achieved",
      "metric": "Quantified result if available",
      "company": "Where it happened"
    }
  ],
  "education": [
    {
      "degree": "Degree name",
      "institution": "School name",
      "field": "Field of study"
    }
  ],
  "publications": ["list of papers/publications if any"],
  "portfolio": ["list of notable projects, repos, or case studies"],
  "locations": ["cities/countries worked in"],
  "remote_ok": true/false based on any remote work signals
}

Be precise. Only include what's explicitly in the resume. Don't infer or make up data.
Return ONLY valid JSON, no markdown or explanation."""


def parse_resume(resume_text):
    """Parse resume text into structured profile using GPT-4o-mini."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    print("🔍 Parsing resume with GPT-4o-mini...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"},
        ],
        temperature=0.1,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content
    profile = json.loads(result)

    # Add metadata
    profile["_parsed_at"] = __import__("datetime").datetime.now().isoformat()
    profile["_model"] = "gpt-4o-mini"
    profile["_tokens"] = {
        "prompt": response.usage.prompt_tokens,
        "completion": response.usage.completion_tokens,
        "total": response.usage.total_tokens,
    }

    return profile


def save_profile(profile):
    """Save parsed profile to file."""
    PROFILE_FILE.write_text(json.dumps(profile, indent=2))
    print(f"💾 Profile saved to {PROFILE_FILE.name}")


def load_profile():
    """Load existing parsed profile."""
    if not PROFILE_FILE.exists():
        return None
    return json.loads(PROFILE_FILE.read_text())


def display_profile(profile):
    """Display parsed profile summary."""
    print(f"\n{'=' * 50}")
    print(f"📋 PARSED PROFILE")
    print(f"{'=' * 50}")
    print(f"Name:       {profile.get('name', 'N/A')}")
    print(f"Title:      {profile.get('current_title', 'N/A')}")
    print(f"Company:    {profile.get('current_company', 'N/A')}")
    print(f"Seniority:  {profile.get('seniority', 'N/A')}")
    print(f"Experience: {profile.get('years_experience', 'N/A')} years")
    print(f"Industries: {', '.join(profile.get('industries', []))}")
    print(f"Remote OK:  {profile.get('remote_ok', 'N/A')}")

    skills = profile.get("skills", {})
    if skills.get("technical"):
        print(f"\nTechnical:  {', '.join(skills['technical'][:8])}")
    if skills.get("leadership"):
        print(f"Leadership: {', '.join(skills['leadership'][:5])}")
    if skills.get("domain"):
        print(f"Domain:     {', '.join(skills['domain'][:5])}")

    achievements = profile.get("achievements", [])
    if achievements:
        print(f"\n🏆 Top Achievements:")
        for a in achievements[:5]:
            metric = f" ({a['metric']})" if a.get("metric") else ""
            company = f" @ {a['company']}" if a.get("company") else ""
            print(f"   • {a['description']}{metric}{company}")

    tokens = profile.get("_tokens", {})
    if tokens:
        print(f"\n📊 Tokens used: {tokens.get('total', 'N/A')}")


def run():
    """Run the Parser agent."""
    validate_credentials()

    # Check if profile already exists
    existing = load_profile()
    if existing:
        print("✅ Profile already parsed.")
        display_profile(existing)
        reparse = input("\n   Re-parse? (y/n) → ").strip().lower()
        if reparse != "y":
            return

    # Get resume input
    print("\n📄 Paste your resume text below (press Enter twice when done):\n")
    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
            lines.append(line)
        except EOFError:
            break

    resume_text = "\n".join(lines).strip()

    if not resume_text:
        # Try loading from file
        resume_file = DATA_DIR / "resume.txt"
        if resume_file.exists():
            resume_text = resume_file.read_text().strip()
            print(f"   Loaded resume from {resume_file.name}")
        else:
            print("❌ No resume text provided. Either paste it or save to data/resume.txt")
            return

    if len(resume_text) < 50:
        print("❌ Resume text too short. Paste your full resume.")
        return

    profile = parse_resume(resume_text)
    save_profile(profile)
    display_profile(profile)


if __name__ == "__main__":
    run()

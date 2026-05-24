"""
Agent 4: STAR Analyzer
Matches parsed profile against a Job Description using STAR framework.
Scores each requirement 0-10 with transparent breakdown.
Identifies gaps and tells you exactly what to add to reach a higher score.
"""

import json
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY, validate_credentials, DATA_DIR

PROFILE_FILE = DATA_DIR / "parsed_profile.json"
STAR_OUTPUT_FILE = DATA_DIR / "star_analysis.json"

SYSTEM_PROMPT = """You are a brutally honest career coach using the STAR framework.

STAR = Situation, Task, Action, Result.

Given a Job Description and a candidate's parsed profile, you must:

1. EXTRACT each key requirement from the JD (aim for 5-8 requirements)
2. For each requirement, SCORE the candidate 0-10 using STAR:
   - S (Situation): Does the candidate have experience in a similar context? (0-2.5)
   - T (Task): Did they face similar goals/challenges? (0-2.5)
   - A (Action): Did they take relevant specific actions? (0-2.5)
   - R (Result): Do they have measurable outcomes to prove it? (0-2.5)

3. For each requirement, provide:
   - The STAR breakdown with evidence from the profile
   - What's MISSING (be specific)
   - What to ADD (portfolio link, metric, case study) to increase the score
   - The honest score with reasoning

4. Calculate an OVERALL FIT SCORE (weighted average)

5. Give a VERDICT: be honest. "You're a 7/10 — here's exactly what gets you to 9/10"

Return JSON in this exact format:
{
  "job_title": "extracted job title",
  "company": "company name if mentioned",
  "overall_score": 7.5,
  "verdict": "One paragraph honest assessment",
  "requirements": [
    {
      "requirement": "What the JD asks for",
      "score": 7,
      "star": {
        "situation": {"score": 2.0, "evidence": "What matches", "gap": "What's missing"},
        "task": {"score": 2.0, "evidence": "...", "gap": "..."},
        "action": {"score": 1.5, "evidence": "...", "gap": "..."},
        "result": {"score": 1.5, "evidence": "...", "gap": "..."}
      },
      "what_to_add": "Specific advice to increase this score"
    }
  ],
  "strengths": ["Top 3 strengths for this role"],
  "critical_gaps": ["Top 3 gaps that could disqualify"],
  "proof_requests": ["Specific portfolio items, case studies, or metrics to prepare"]
}

RULES:
- Be HONEST. Don't inflate scores to be nice.
- A 5/10 means "meets half the bar" — don't give 7 when you mean 5.
- If there's no evidence for something, score it 0-1, not 3-4.
- "What to add" must be SPECIFIC and ACTIONABLE, not generic advice.
- Reference the candidate's actual achievements by name when they match.
- Return ONLY valid JSON."""


def load_profile():
    """Load parsed profile."""
    if not PROFILE_FILE.exists():
        print("❌ No parsed profile found. Run parser.py first.")
        return None
    return json.loads(PROFILE_FILE.read_text())


def analyze_fit(jd_text, profile):
    """Run STAR analysis on JD against profile."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    profile_str = json.dumps(profile, indent=2)

    print("🔍 Running STAR analysis with GPT-4o-mini...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"JOB DESCRIPTION:\n{jd_text}\n\nCANDIDATE PROFILE:\n{profile_str}"},
        ],
        temperature=0.2,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    result["_tokens"] = {
        "prompt": response.usage.prompt_tokens,
        "completion": response.usage.completion_tokens,
        "total": response.usage.total_tokens,
    }

    return result


def display_analysis(analysis):
    """Display STAR analysis results."""
    print(f"\n{'=' * 60}")
    print(f"⭐ STAR ANALYSIS: {analysis.get('job_title', 'Unknown Role')}")
    if analysis.get("company"):
        print(f"   Company: {analysis['company']}")
    print(f"{'=' * 60}")

    overall = analysis.get("overall_score", 0)
    bar = "█" * int(overall) + "░" * (10 - int(overall))
    print(f"\n   OVERALL FIT: [{bar}] {overall}/10\n")

    # Requirements breakdown
    requirements = analysis.get("requirements", [])
    for i, req in enumerate(requirements, 1):
        score = req.get("score", 0)
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"   {i}. {req['requirement']}")
        print(f"      Score: [{bar}] {score}/10")

        star = req.get("star", {})
        for component in ["situation", "task", "action", "result"]:
            s = star.get(component, {})
            label = component[0].upper()
            evidence = s.get("evidence", "N/A")
            gap = s.get("gap", "")
            cscore = s.get("score", 0)
            status = "✅" if cscore >= 2.0 else "⚠️" if cscore >= 1.0 else "❌"
            print(f"      {status} {label}: {evidence[:80]}")
            if gap and gap.lower() not in ("none", "n/a", "no gap"):
                print(f"         Gap: {gap[:80]}")

        if req.get("what_to_add"):
            print(f"      💡 Add: {req['what_to_add'][:100]}")
        print()

    # Strengths
    strengths = analysis.get("strengths", [])
    if strengths:
        print(f"   ✅ STRENGTHS:")
        for s in strengths:
            print(f"      • {s}")

    # Critical gaps
    gaps = analysis.get("critical_gaps", [])
    if gaps:
        print(f"\n   ❌ CRITICAL GAPS:")
        for g in gaps:
            print(f"      • {g}")

    # Proof requests
    proofs = analysis.get("proof_requests", [])
    if proofs:
        print(f"\n   📎 PROOF TO PREPARE:")
        for p in proofs:
            print(f"      • {p}")

    # Verdict
    verdict = analysis.get("verdict", "")
    if verdict:
        print(f"\n   📣 VERDICT:")
        print(f"      {verdict[:300]}")

    tokens = analysis.get("_tokens", {})
    print(f"\n   📊 Tokens used: {tokens.get('total', 'N/A')}")


def run():
    """Run the STAR agent."""
    validate_credentials()

    profile = load_profile()
    if not profile:
        return

    print(f"✅ Profile loaded: {profile.get('name', 'Unknown')}")
    print(f"   {profile.get('current_title', '')} @ {profile.get('current_company', '')}")
    print(f"   {profile.get('years_experience', '?')} years | {profile.get('seniority', '?')} level\n")

    # Get JD input
    print("📋 Paste the Job Description below (press Enter twice when done):\n")
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

    jd_text = "\n".join(lines).strip()

    if not jd_text:
        # Try loading from file
        jd_file = DATA_DIR / "jd.txt"
        if jd_file.exists():
            jd_text = jd_file.read_text().strip()
            print(f"   Loaded JD from {jd_file.name}")
        else:
            print("❌ No JD provided. Paste it or save to data/jd.txt")
            return

    if len(jd_text) < 50:
        print("❌ JD text too short.")
        return

    analysis = analyze_fit(jd_text, profile)

    # Save
    STAR_OUTPUT_FILE.write_text(json.dumps(analysis, indent=2))
    print(f"💾 Analysis saved to {STAR_OUTPUT_FILE.name}")

    display_analysis(analysis)


if __name__ == "__main__":
    run()

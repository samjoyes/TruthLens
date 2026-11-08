"""Text analysis module for clickbait detection, consistency checking, and claim extraction."""

import re
from typing import Optional

from core.llm import generate_structured
from core.schemas import TextAnalysis

CLICKBAIT_PATTERNS = [
    r"\byou won'?t believe\b",
    r"\bshocking\b",
    r"\bwill blow your mind\b",
    r"\bwhat happens next\b",
    r"\bthis one trick\b",
    r"\bsee why\b",
    r"\bunbelievable\b",
    r"\bsecret revealed\b",
    r"\bbreaks silence\b",
    r"\bgoes viral\b",
    r"\bthe truth about\b",
    r"\bcan't stop laughing\b",
    r"\bdisturbing details\b",
]


def compute_clickbait_heuristic(headline: str) -> int:
    """Calculate a rule-based clickbait score (0-100) using textual heuristics."""
    if not headline or not headline.strip():
        return 0

    score = 0
    clean_headline = headline.strip()

    # 1. Check for clickbait pattern matches
    lower_headline = clean_headline.lower()
    pattern_matches = sum(1 for pattern in CLICKBAIT_PATTERNS if re.search(pattern, lower_headline))
    score += pattern_matches * 25

    # 2. Check for exclamation marks and question marks
    exclamation_count = clean_headline.count("!")
    if exclamation_count > 0:
        score += min(exclamation_count * 15, 30)

    if clean_headline.endswith("?") or "?" in clean_headline:
        score += 15

    # 3. Check for ALL CAPS words (excluding short words like I, US, UK, AI, etc.)
    words = re.findall(r"\b[A-Z]{3,}\b", clean_headline)
    if words:
        score += min(len(words) * 20, 35)

    # 4. Number bait (e.g., "7 reasons why", "Top 10")
    if re.match(r"^\d+\s+(reasons|ways|things|secrets|tricks)", lower_headline):
        score += 20

    return max(0, min(100, score))


def analyze_text(headline: str, body: Optional[str] = None) -> TextAnalysis:
    """Analyze news text for clickbait, sensationalism, headline consistency, and extract claims.

    Args:
        headline: The news title or headline.
        body: Optional article text.

    Returns:
        TextAnalysis with scores and extracted verifiable claims.
    """
    cleaned_headline = (headline or "").strip()
    has_body = bool(body and body.strip())
    truncated_body = (body.strip()[:6000]) if has_body else ""

    body_section = (
        f"BODY: {truncated_body}"
        if has_body
        else "BODY: [None provided. Evaluate consistency neutrally at 50, note this in reasoning.]"
    )

    prompt = f"""You are a careful news-credibility analyst. Analyze the news item below.
Return ONLY JSON matching the schema.
- clickbait_score: 0-100, 100 = extreme clickbait (curiosity gap, exaggeration, sensational wording, unsupported superlatives)
- sensationalism_score: 0-100
- headline_body_consistency: 0-100, 100 = headline fully supported by body. If no body provided, set to 50.
- key_claims: up to 3 concrete, checkable factual claims (names, numbers, events, dates) from the headline/body rather than opinions.
- reasoning: 2-3 sentences, plain language explaining the scores.

HEADLINE: {cleaned_headline}
{body_section}
"""

    analysis: TextAnalysis = generate_structured(prompt=prompt, schema=TextAnalysis, temperature=0.2)

    # Blend LLM clickbait score with heuristic score (0.7 LLM + 0.3 heuristic)
    heuristic_score = compute_clickbait_heuristic(cleaned_headline)
    blended_clickbait = int(round(0.7 * analysis.clickbait_score + 0.3 * heuristic_score))
    blended_clickbait = max(0, min(100, blended_clickbait))

    # Ensure key claims are at most 3
    final_claims = [c.strip() for c in analysis.key_claims if c.strip()][:3]

    final_consistency = analysis.headline_body_consistency
    final_reasoning = analysis.reasoning
    if not has_body:
        final_consistency = 50
        if "no body" not in final_reasoning.lower():
            final_reasoning += " (Evaluated headline-only; consistency set to neutral 50)."

    return TextAnalysis(
        clickbait_score=blended_clickbait,
        sensationalism_score=analysis.sensationalism_score,
        headline_body_consistency=final_consistency,
        key_claims=final_claims,
        reasoning=final_reasoning,
    )

"""Scoring and verdict aggregation engine."""

from typing import Literal, Optional

from core.config import (
    WEIGHT_CLAIM_VERIFICATION,
    WEIGHT_CLICKBAIT,
    WEIGHT_CONSISTENCY,
    WEIGHT_IMAGE,
)
from core.llm import LLMError, generate_structured
from core.schemas import ClaimResult, ImageAnalysis, Source, TextAnalysis
from pydantic import BaseModel


class ExplanationOutput(BaseModel):
    explanation: str


def compute_claim_score(claim_results: list[ClaimResult]) -> float:
    """Compute numerical score (0-100) from claim verification outcomes."""
    if not claim_results:
        return 50.0  # Neutral score if no verifiable claims are present

    weights = {"Supported": 100.0, "Unverified": 50.0, "Contradicted": 0.0}
    scores = [weights.get(cr.status, 50.0) for cr in claim_results]
    return sum(scores) / len(scores)


def compute_credibility(
    claim_score: float,
    consistency: int,
    clickbait_score: int,
    image_manipulation: Optional[int] = None,
) -> int:
    """Calculate aggregated credibility score (0-100) using weighted linear combination."""
    clickbait_ok = 100 - clickbait_score

    if image_manipulation is not None:
        image_ok = 100 - image_manipulation
        raw = (
            WEIGHT_CLAIM_VERIFICATION * claim_score
            + WEIGHT_CONSISTENCY * consistency
            + WEIGHT_CLICKBAIT * clickbait_ok
            + WEIGHT_IMAGE * image_ok
        )
    else:
        # Proportionally redistribute the 15% image weight across remaining components
        denom = WEIGHT_CLAIM_VERIFICATION + WEIGHT_CONSISTENCY + WEIGHT_CLICKBAIT
        w_claim = WEIGHT_CLAIM_VERIFICATION / denom
        w_cons = WEIGHT_CONSISTENCY / denom
        w_click = WEIGHT_CLICKBAIT / denom

        raw = (w_claim * claim_score) + (w_cons * consistency) + (w_click * clickbait_ok)

    return max(0, min(100, int(round(raw))))


def determine_verdict(
    credibility: int,
    clickbait_score: int,
    consistency: int,
    claim_results: list[ClaimResult],
) -> Literal["Real", "Misleading", "Fake"]:
    """Determine the final discrete verdict according to specified threshold rules."""
    total_claims = len(claim_results)
    contradicted_count = sum(1 for c in claim_results if c.status == "Contradicted")
    majority_contradicted = total_claims > 0 and (contradicted_count > total_claims / 2.0)

    # Fake rule: credibility < 40 or majority claims Contradicted
    if credibility < 40 or majority_contradicted:
        return "Fake"

    # Misleading rule: credibility 40..69 or clickbait_score >= 70 or consistency < 50 or has contradicted claim
    if (
        (40 <= credibility <= 69)
        or clickbait_score >= 70
        or consistency < 50
        or (contradicted_count > 0)
    ):
        return "Misleading"

    # Real rule: credibility >= 70 and no Contradicted claim
    if credibility >= 70 and contradicted_count == 0:
        return "Real"

    return "Misleading"


def compute_confidence(
    credibility: int,
    claim_results: list[ClaimResult],
    total_sources_count: int,
) -> int:
    """Calculate confidence score (5-95) based on margin of certainty and evidence quality."""
    # Distance from the uncertain midpoint (50)
    start = int(round(abs(credibility - 50) * 2))

    total_claims = len(claim_results)
    unverified_count = sum(1 for c in claim_results if c.status == "Unverified")

    # Reduce by 20 if most claims are Unverified or no claims found
    if total_claims == 0 or (unverified_count > total_claims / 2.0):
        start -= 20

    # Reduce by 10 if fewer than 2 sources were found
    if total_sources_count < 2:
        start -= 10

    # Clamp to [5, 95]
    return max(5, min(95, start))


def generate_explanation(
    headline: str,
    verdict: str,
    credibility: int,
    confidence: int,
    text_analysis: TextAnalysis,
    claim_results: list[ClaimResult],
    citations: list[Source],
    image_analysis: Optional[ImageAnalysis] = None,
) -> str:
    """Generate a coherent 3-4 sentence explanation using Gemini, with a deterministic fallback."""
    top_source = citations[0].title if citations else "available web records"

    claims_summary = "; ".join(f"'{c.claim}' ({c.status})" for c in claim_results) or "No specific verifiable claims"
    if image_analysis:
        img_summary = (
            f"Image assessment verdict: {image_analysis.verdict} (suspicion: {image_analysis.manipulation_suspicion}%, match: {image_analysis.context_match}%).\n"
            f"Detected visual entities: {', '.join(image_analysis.detected_entities) if image_analysis.detected_entities else 'None'}.\n"
            f"Identified origin context: {image_analysis.origin_context or 'Not specified'}.\n"
            f"Visual reasoning: {image_analysis.reasoning}"
        )
    else:
        img_summary = "No image was provided."

    prompt = f"""Summarize the news authenticity / image verification analysis below into 3-4 clear, objective plain sentences for a reader.
Explain what the image/story depicts, its verified origin, key facts discovered, and reference the most important source ({top_source}).

Headline/Subject: {headline}
Verdict: {verdict} (Credibility: {credibility}%, Confidence: {confidence}%)
Text Analysis: Clickbait score {text_analysis.clickbait_score}/100, Consistency {text_analysis.headline_body_consistency}/100.
Verified Search Findings: {claims_summary}
{img_summary}

Return ONLY valid JSON:
- explanation: 3-4 plain sentences
"""
    try:
        res = generate_structured(prompt=prompt, schema=ExplanationOutput, temperature=0.2)
        if res.explanation and len(res.explanation.strip()) > 20:
            return res.explanation.strip()
    except (LLMError, Exception):
        pass

    # Deterministic fallback explanation
    if image_analysis and ("Reverse Image Deep Dive" in headline or not text_analysis.clickbait_score):
        origin = image_analysis.origin_context or "the image"
        entities = ", ".join(image_analysis.detected_entities[:3]) if image_analysis.detected_entities else "visual elements"
        return (
            f"TruthLens investigated this media and identified {entities}. "
            f"Contextual records indicate {origin}. "
            f"Web search findings across sources like {top_source} verify the media with {credibility}% credibility and {confidence}% confidence."
        )

    fallback = (
        f"TruthLens evaluated '{headline}' with a verdict of {verdict} ({credibility}% credibility, {confidence}% confidence). "
        f"The headline has a clickbait score of {text_analysis.clickbait_score}/100 and a headline-body consistency of {text_analysis.headline_body_consistency}/100. "
        f"Evidence retrieved from sources such as {top_source} was analyzed against the extracted claims to establish this assessment."
    )
    return fallback

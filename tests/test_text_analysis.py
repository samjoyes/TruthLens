"""Unit tests for text analysis and clickbait heuristics."""

from unittest.mock import patch
from core.schemas import TextAnalysis
from core.text_analysis import analyze_text, compute_clickbait_heuristic


def test_clickbait_heuristic_detection():
    """Verify clickbait patterns, ALL CAPS, and punctuation are scored high."""
    clickbait_headline = "YOU WON'T BELIEVE WHAT HAPPENS NEXT! SHOCKING TRUTH REVEALED!!!"
    score = compute_clickbait_heuristic(clickbait_headline)
    assert score >= 70

    neutral_headline = "Reserve Bank of India maintains benchmark interest rate at 6.5%"
    score_neutral = compute_clickbait_heuristic(neutral_headline)
    assert score_neutral == 0


def test_analyze_text_blends_heuristic():
    """Verify LLM score and heuristic score blend correctly."""
    mock_llm_res = TextAnalysis(
        clickbait_score=80,
        sensationalism_score=75,
        headline_body_consistency=30,
        key_claims=["Claim 1", "Claim 2"],
        reasoning="Sensational framing.",
    )
    with patch("core.text_analysis.generate_structured", return_value=mock_llm_res):
        res = analyze_text("YOU WON'T BELIEVE THIS SHOCKING DISCOVERY!", "Body text here.")
        assert isinstance(res, TextAnalysis)
        # Both LLM and heuristic should contribute to high clickbait score
        assert res.clickbait_score >= 70
        assert res.headline_body_consistency == 30
        assert len(res.key_claims) == 2


def test_analyze_text_empty_body_fallback():
    """Verify headline-only analysis sets consistency to neutral 50."""
    mock_llm_res = TextAnalysis(
        clickbait_score=10,
        sensationalism_score=15,
        headline_body_consistency=95,
        key_claims=["Launch scheduled for Friday"],
        reasoning="Clear and factual.",
    )
    with patch("core.text_analysis.generate_structured", return_value=mock_llm_res):
        res = analyze_text("Rocket launch scheduled for Friday", body="")
        assert res.headline_body_consistency == 50
        assert "neutral 50" in res.reasoning

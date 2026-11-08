"""Unit tests for Pydantic schemas in core/schemas.py."""

import pytest
from pydantic import ValidationError

from core.schemas import (
    AnalysisResult,
    ClaimResult,
    ImageAnalysis,
    Source,
    TextAnalysis,
)


def test_valid_text_analysis():
    """Verify that valid TextAnalysis data passes validation."""
    data = TextAnalysis(
        clickbait_score=30,
        sensationalism_score=25,
        headline_body_consistency=85,
        key_claims=["Claim 1", "Claim 2"],
        reasoning="Sensible and factual report.",
    )
    assert data.clickbait_score == 30
    assert data.sensationalism_score == 25
    assert data.headline_body_consistency == 85
    assert len(data.key_claims) == 2
    assert data.reasoning == "Sensible and factual report."


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("clickbait_score", -1),
        ("clickbait_score", 101),
        ("sensationalism_score", -10),
        ("sensationalism_score", 150),
        ("headline_body_consistency", -5),
        ("headline_body_consistency", 105),
    ],
)
def test_text_analysis_out_of_range(field, invalid_value):
    """Verify out-of-range integer scores trigger ValidationError."""
    payload = {
        "clickbait_score": 10,
        "sensationalism_score": 10,
        "headline_body_consistency": 90,
        "key_claims": ["Test claim"],
        "reasoning": "Reasoning here",
    }
    payload[field] = invalid_value
    with pytest.raises(ValidationError):
        TextAnalysis(**payload)


def test_valid_image_analysis():
    """Verify valid ImageAnalysis instantiation."""
    img = ImageAnalysis(
        manipulation_suspicion=15,
        context_match=95,
        verdict="Consistent",
        reasoning="Image reflects described event accurately.",
    )
    assert img.verdict == "Consistent"
    assert img.manipulation_suspicion == 15
    assert img.context_match == 95


def test_image_analysis_invalid_verdict():
    """Verify invalid verdict in ImageAnalysis fails."""
    with pytest.raises(ValidationError):
        ImageAnalysis(
            manipulation_suspicion=10,
            context_match=90,
            verdict="Uncertain",  # Not in Literal
            reasoning="Invalid verdict test",
        )


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("manipulation_suspicion", -1),
        ("manipulation_suspicion", 101),
        ("context_match", -1),
        ("context_match", 101),
    ],
)
def test_image_analysis_out_of_range(field, invalid_value):
    """Verify out-of-range image scores raise ValidationError."""
    payload = {
        "manipulation_suspicion": 20,
        "context_match": 80,
        "verdict": "Consistent",
        "reasoning": "Test reasoning",
    }
    payload[field] = invalid_value
    with pytest.raises(ValidationError):
        ImageAnalysis(**payload)


def test_valid_source_defaults():
    """Verify default values in Source."""
    src = Source(title="BBC News", url="https://bbc.com/news/123")
    assert src.snippet == ""
    assert src.stance == "neutral"


def test_source_invalid_stance():
    """Verify invalid stance in Source fails validation."""
    with pytest.raises(ValidationError):
        Source(
            title="BBC News",
            url="https://bbc.com/news/123",
            stance="disagrees",  # Invalid stance literal
        )


def test_claim_result():
    """Verify ClaimResult model with sources."""
    cr = ClaimResult(
        claim="ISRO launched Chandrayaan-3",
        status="Supported",
        reasoning="Confirmed by multiple official reports.",
        sources=[Source(title="ISRO", url="https://isro.gov.in", stance="supports")],
    )
    assert cr.status == "Supported"
    assert len(cr.sources) == 1
    assert cr.sources[0].stance == "supports"


def test_claim_result_invalid_status():
    """Verify invalid status in ClaimResult fails."""
    with pytest.raises(ValidationError):
        ClaimResult(
            claim="ISRO launched Chandrayaan-3",
            status="Confirmed",  # Not in Literal
            reasoning="Invalid status test",
        )


def test_analysis_result_serialization():
    """Verify end-to-end AnalysisResult validation and JSON serialization."""
    text_analysis = TextAnalysis(
        clickbait_score=15,
        sensationalism_score=20,
        headline_body_consistency=90,
        key_claims=["Spacecraft entered orbit"],
        reasoning="Reliable reporting",
    )
    analysis = AnalysisResult(
        verdict="Real",
        confidence=90,
        credibility_score=88,
        explanation="The story is well supported by primary sources.",
        text_analysis=text_analysis,
        image_analysis=None,
        claim_results=[
            ClaimResult(
                claim="Spacecraft entered orbit",
                status="Supported",
                reasoning="Confirmed by telemetry.",
                sources=[
                    Source(
                        title="Space Agency",
                        url="https://example.com/orbit",
                        stance="supports",
                    )
                ],
            )
        ],
        citations=[Source(title="Space Agency", url="https://example.com/orbit")],
    )

    json_str = analysis.model_dump_json()
    loaded = AnalysisResult.model_validate_json(json_str)
    assert loaded.verdict == "Real"
    assert loaded.confidence == 90
    assert loaded.credibility_score == 88
    assert loaded.image_analysis is None
    assert len(loaded.claim_results) == 1


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("confidence", -5),
        ("confidence", 101),
        ("credibility_score", -1),
        ("credibility_score", 150),
    ],
)
def test_analysis_result_out_of_range(field, invalid_value):
    """Verify out-of-range confidence or credibility_score raises ValidationError."""
    text_analysis = TextAnalysis(
        clickbait_score=10,
        sensationalism_score=10,
        headline_body_consistency=90,
        key_claims=["Claim"],
        reasoning="Reasoning",
    )
    payload = {
        "verdict": "Real",
        "confidence": 85,
        "credibility_score": 80,
        "explanation": "Valid explanation",
        "text_analysis": text_analysis,
        "claim_results": [],
        "citations": [],
    }
    payload[field] = invalid_value
    with pytest.raises(ValidationError):
        AnalysisResult(**payload)

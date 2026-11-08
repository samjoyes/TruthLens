"""Unit tests for scoring and verdict aggregation (core/scoring.py)."""

import pytest
from core.schemas import ClaimResult, Source
from core.scoring import (
    compute_claim_score,
    compute_confidence,
    compute_credibility,
    determine_verdict,
)


def _make_source(title="Source", url="https://example.com"):
    return Source(title=title, url=url)


# 1. Clean real news (high credibility, low clickbait, high consistency, supported claims, no contradicted)
def test_clean_real_news():
    claims = [
        ClaimResult(claim="Claim 1", status="Supported", reasoning="verified"),
        ClaimResult(claim="Claim 2", status="Supported", reasoning="verified"),
    ]
    claim_score = compute_claim_score(claims)
    assert claim_score == 100.0

    credibility = compute_credibility(
        claim_score=claim_score,
        consistency=95,
        clickbait_score=10,
        image_manipulation=5,
    )
    assert credibility >= 70

    verdict = determine_verdict(credibility, clickbait_score=10, consistency=95, claim_results=claims)
    assert verdict == "Real"

    confidence = compute_confidence(credibility, claims, total_sources_count=3)
    assert confidence > 70


# 2. Pure clickbait (high clickbait >= 70, medium-high credibility) -> Misleading
def test_pure_clickbait():
    claims = [ClaimResult(claim="Event happened", status="Supported", reasoning="true")]
    claim_score = compute_claim_score(claims)
    credibility = compute_credibility(claim_score, consistency=80, clickbait_score=85, image_manipulation=0)

    verdict = determine_verdict(credibility, clickbait_score=85, consistency=80, claim_results=claims)
    assert verdict == "Misleading"


# 3. Contradicted claim (majority contradicted) -> Fake
def test_majority_contradicted_claim():
    claims = [
        ClaimResult(claim="Claim 1", status="Contradicted", reasoning="false"),
        ClaimResult(claim="Claim 2", status="Contradicted", reasoning="false"),
        ClaimResult(claim="Claim 3", status="Supported", reasoning="minor fact"),
    ]
    claim_score = compute_claim_score(claims)
    assert claim_score < 40

    credibility = compute_credibility(claim_score, consistency=40, clickbait_score=50, image_manipulation=None)
    verdict = determine_verdict(credibility, clickbait_score=50, consistency=40, claim_results=claims)
    assert verdict == "Fake"


# 4. No image provided (weights redistributed)
def test_no_image_proportional_redistribution():
    claims = [ClaimResult(claim="Claim 1", status="Supported", reasoning="verified")]
    claim_score = compute_claim_score(claims)
    credibility_no_img = compute_credibility(
        claim_score=claim_score,
        consistency=80,
        clickbait_score=20,
        image_manipulation=None,
    )
    assert 0 <= credibility_no_img <= 100
    # Should evaluate to high credibility (~90)
    assert credibility_no_img >= 85


# 5. No claims found (neutral claim score = 50, confidence penalized)
def test_no_claims_found():
    claims = []
    claim_score = compute_claim_score(claims)
    assert claim_score == 50.0

    credibility = compute_credibility(claim_score, consistency=60, clickbait_score=30, image_manipulation=None)
    # Confidence starts at |credibility - 50| * 2, then penalized by 20 for no claims
    confidence = compute_confidence(credibility, claims, total_sources_count=0)
    assert 5 <= confidence <= 95
    # Since total_sources_count < 2 and no claims, confidence is reduced heavily
    assert confidence <= 40


# 6. All claims unverified (unverified penalty on confidence)
def test_all_claims_unverified():
    claims = [
        ClaimResult(claim="Claim 1", status="Unverified", reasoning="no evidence"),
        ClaimResult(claim="Claim 2", status="Unverified", reasoning="no evidence"),
    ]
    claim_score = compute_claim_score(claims)
    assert claim_score == 50.0

    credibility = compute_credibility(claim_score, consistency=50, clickbait_score=50, image_manipulation=None)
    assert credibility == 50

    confidence = compute_confidence(credibility, claims, total_sources_count=2)
    # At credibility=50, start is 0, reduced by 20, clamped to 5
    assert confidence == 5

    verdict = determine_verdict(credibility, clickbait_score=50, consistency=50, claim_results=claims)
    assert verdict == "Misleading"


# 7. Determinism: Same inputs always give the exact same verdict & scores
def test_determinism_consistency():
    claims = [
        ClaimResult(claim="Fact A", status="Supported", reasoning="ok"),
        ClaimResult(claim="Fact B", status="Contradicted", reasoning="bad"),
    ]
    score1 = compute_credibility(50.0, 70, 30, 20)
    score2 = compute_credibility(50.0, 70, 30, 20)
    assert score1 == score2

    v1 = determine_verdict(score1, 30, 70, claims)
    v2 = determine_verdict(score2, 30, 70, claims)
    assert v1 == v2

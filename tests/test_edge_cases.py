"""Unit tests verifying TruthLens resilience against critical edge cases."""

from unittest.mock import MagicMock, patch
import pytest

from core.image_analysis import validate_and_preprocess_image
from core.pipeline import run_analysis
from core.retrieval import fetch_article, is_safe_url, search_web
from core.schemas import AnalysisResult, ClaimResult, Source, TextAnalysis


def test_edge_case_huge_image_rejected():
    """Images exceeding 5 MB must raise ValueError."""
    huge_bytes = b"0" * (6 * 1024 * 1024)  # 6 MB
    with pytest.raises(ValueError) as exc:
        validate_and_preprocess_image(huge_bytes)
    assert "exceeds maximum allowed 5 MB" in str(exc.value)


def test_edge_case_wrong_image_type_rejected():
    """Non-image bytes or invalid image headers must raise ValueError."""
    fake_bytes = b"This is plain text pretending to be an image."
    with pytest.raises(ValueError) as exc:
        validate_and_preprocess_image(fake_bytes)
    assert "Unable to read image" in str(exc.value)


def test_edge_case_broken_url_fails_safely():
    """HTTP 404 or connection failures in fetch_article must return empty tuple safely."""
    with patch("core.retrieval.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_resp

        title, body = fetch_article("https://news.example.com/missing-404")
        assert title == ""
        assert body == ""


def test_edge_case_paywalled_page_handled():
    """Paywalled or blocked pages returning empty body are handled safely."""
    with patch("core.retrieval.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = "<html><head><title>Subscription Required</title></head><body></body></html>"
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        title, body = fetch_article("https://news.example.com/paywall")
        assert title == "Subscription Required"
        assert body == ""


def test_edge_case_no_internet_in_search():
    """Network failure during DDGS search must return empty list without crash."""
    with patch("core.retrieval.DDGS") as mock_ddgs, patch("core.retrieval.requests.get") as mock_requests:
        mock_ddgs.side_effect = Exception("Network is unreachable")
        mock_requests.side_effect = Exception("Network is unreachable")

        results = search_web("Breaking news headline")
        assert results == []


def test_edge_case_very_short_headline(tmp_path):
    """Very short headline runs through pipeline without IndexError or crash."""
    db_file = str(tmp_path / "edge_test.db")
    mock_text = TextAnalysis(
        clickbait_score=20,
        sensationalism_score=20,
        headline_body_consistency=50,
        key_claims=["War"],
        reasoning="Extremely brief statement.",
    )
    with (
        patch("core.pipeline.analyze_text", return_value=mock_text),
        patch("core.verification.verify_claims_parallel", return_value=[]),
        patch("core.scoring.generate_explanation", return_value="Short headline evaluated."),
    ):
        result = run_analysis(headline="War", db_path=db_file)
        assert isinstance(result, AnalysisResult)
        assert result.text_analysis.clickbait_score == 20


def test_edge_case_non_english_headline(tmp_path):
    """Non-English text executes properly through the pipeline."""
    db_file = str(tmp_path / "edge_test_intl.db")
    mock_text = TextAnalysis(
        clickbait_score=10,
        sensationalism_score=15,
        headline_body_consistency=90,
        key_claims=["Chandrayaan 3 chandra par utara"],
        reasoning="Hindi headline reporting lunar landing.",
    )
    with (
        patch("core.pipeline.analyze_text", return_value=mock_text),
        patch("core.verification.verify_claims_parallel", return_value=[]),
        patch("core.scoring.generate_explanation", return_value="International headline analyzed."),
    ):
        result = run_analysis(
            headline="चंद्रयान-3 चंद्रमा के दक्षिणी ध्रुव पर सफलतापूर्वक उतरा",
            db_path=db_file,
        )
        assert isinstance(result, AnalysisResult)
        assert result.verdict in ("Real", "Misleading", "Fake")

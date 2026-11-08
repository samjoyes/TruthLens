"""Unit and integration tests for the TruthLens analysis pipeline (core/pipeline.py)."""

from unittest.mock import MagicMock, patch
import pytest

from core.db import get_analysis, init_db, list_history
from core.pipeline import run_analysis
from core.schemas import AnalysisResult, ClaimResult, ImageAnalysis, Source, TextAnalysis


def test_pipeline_rejects_empty_input():
    """Verify ValueError is raised if neither URL, headline, nor image is provided."""
    with pytest.raises(ValueError) as exc:
        run_analysis(url="", headline="", image_bytes=None)
    assert "Please provide an image" in str(exc.value)


def test_pipeline_end_to_end_mocked(tmp_path):
    """Verify full pipeline flow: text -> verification -> scoring -> explanation -> DB."""
    db_file = str(tmp_path / "pipeline_test.db")
    init_db(db_path=db_file)

    mock_text = TextAnalysis(
        clickbait_score=15,
        sensationalism_score=20,
        headline_body_consistency=90,
        key_claims=["India landed on lunar south pole"],
        reasoning="Factual report.",
    )

    mock_claims = [
        ClaimResult(
            claim="India landed on lunar south pole",
            status="Supported",
            reasoning="Confirmed by ISRO.",
            sources=[Source(title="ISRO", url="https://isro.gov.in", stance="supports")],
        )
    ]

    progress_log = []

    def mock_progress(msg: str):
        progress_log.append(msg)

    with (
        patch("core.pipeline.analyze_text", return_value=mock_text),
        patch("core.verification.verify_claims_parallel", return_value=mock_claims),
        patch("core.scoring.generate_explanation", return_value="Verified real report."),
    ):
        result = run_analysis(
            headline="Chandrayaan-3 successfully soft lands on Moon",
            body="ISRO achieved touchdown near the lunar south pole.",
            progress_callback=mock_progress,
            db_path=db_file,
        )

        assert isinstance(result, AnalysisResult)
        assert result.verdict == "Real"
        assert result.credibility_score >= 70
        assert len(result.claim_results) == 1
        assert len(result.citations) == 1
        assert len(progress_log) >= 3

        # Verify persisted into SQLite
        history = list_history(limit=5, db_path=db_file)
        assert len(history) == 1
        assert history[0]["headline"] == "Chandrayaan-3 successfully soft lands on Moon"
        assert history[0]["verdict"] == "Real"


def test_pipeline_image_only_reverse_search(tmp_path):
    """Verify image-only investigation without headline performs reverse search."""
    db_file = str(tmp_path / "pipeline_img_test.db")
    init_db(db_path=db_file)

    mock_img_analysis = ImageAnalysis(
        manipulation_suspicion=10,
        context_match=90,
        verdict="Consistent",
        reasoning="Authentic photograph of historical launch.",
        detected_entities=["LVM3 Rocket", "Sriharikota"],
        reverse_search_queries=["ISRO Chandrayaan-3 launch Sriharikota"],
        origin_context="ISRO Chandrayaan-3 launch on July 14, 2023",
    )

    mock_claims = [
        ClaimResult(
            claim="ISRO Chandrayaan-3 launch Sriharikota",
            status="Supported",
            reasoning="Confirmed by historical mission records.",
            sources=[Source(title="ISRO", url="https://isro.gov.in", stance="supports")],
        )
    ]

    with (
        patch("core.pipeline.analyze_image", return_value=mock_img_analysis),
        patch("core.verification.verify_claims_parallel", return_value=mock_claims),
        patch("core.scoring.generate_explanation", return_value="Reverse search confirms image."),
    ):
        # Pass dummy non-empty image bytes with no headline or URL
        result = run_analysis(image_bytes=b"fake_image_bytes", db_path=db_file)

        assert isinstance(result, AnalysisResult)
        assert result.verdict == "Real"
        assert result.image_analysis is not None
        assert "LVM3 Rocket" in result.image_analysis.detected_entities
        assert len(result.citations) >= 1

        history = list_history(limit=1, db_path=db_file)
        assert len(history) == 1
        assert history[0]["input_type"] == "image_only"


def test_pipeline_story_only_input(tmp_path):
    """Verify pipeline functions when ONLY story body is provided without headline or URL."""
    db_file = str(tmp_path / "pipeline_story_test.db")
    init_db(db_path=db_file)

    mock_text = TextAnalysis(
        clickbait_score=5,
        sensationalism_score=10,
        headline_body_consistency=95,
        key_claims=["128 shinkin banks affected by outage"],
        reasoning="Factual report on banking disruption.",
    )

    mock_claims = [
        ClaimResult(
            claim="128 shinkin banks affected by outage",
            status="Supported",
            reasoning="Confirmed by banking association.",
            sources=[Source(title="Financial News", url="https://example.com/banks", stance="supports")],
        )
    ]

    with (
        patch("core.pipeline.analyze_text", return_value=mock_text),
        patch("core.verification.verify_claims_parallel", return_value=mock_claims),
        patch("core.scoring.generate_explanation", return_value="Bank failure verified."),
    ):
        result = run_analysis(
            body="a major system failure disrupted 128 shinkin banks across the region.",
            db_path=db_file,
        )

        assert isinstance(result, AnalysisResult)
        assert result.verdict == "Real"
        assert len(result.claim_results) == 1
        assert len(result.citations) == 1

        history = list_history(limit=1, db_path=db_file)
        assert len(history) == 1
        assert "a major system failure disrupted 128 shinkin banks" in history[0]["headline"]

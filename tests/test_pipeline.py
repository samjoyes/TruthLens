"""Unit and integration tests for the TruthLens analysis pipeline (core/pipeline.py)."""

from unittest.mock import MagicMock, patch
import pytest

from core.db import get_analysis, init_db, list_history
from core.pipeline import run_analysis
from core.schemas import AnalysisResult, ClaimResult, ImageAnalysis, Source, TextAnalysis


def test_pipeline_rejects_empty_input():
    """Verify ValueError is raised if neither URL nor headline is provided."""
    with pytest.raises(ValueError) as exc:
        run_analysis(url="", headline="")
    assert "either a news URL or a headline" in str(exc.value)


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

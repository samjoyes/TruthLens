"""Unit tests for the SQLite database layer (core/db.py)."""

from core.db import delete_analysis, get_analysis, init_db, list_history, save_analysis
from core.schemas import AnalysisResult, ClaimResult, Source, TextAnalysis


def _make_dummy_result(headline: str = "Test Headline", verdict: str = "Real") -> AnalysisResult:
    """Helper to construct a valid AnalysisResult fixture."""
    return AnalysisResult(
        verdict=verdict,
        confidence=92,
        credibility_score=85,
        explanation=f"Explanation for {headline}",
        text_analysis=TextAnalysis(
            clickbait_score=10,
            sensationalism_score=15,
            headline_body_consistency=90,
            key_claims=["Claim A"],
            reasoning="Reasoning A",
        ),
        image_analysis=None,
        claim_results=[
            ClaimResult(
                claim="Claim A",
                status="Supported",
                reasoning="Verified via search.",
                sources=[Source(title="Official Source", url="https://example.com/source")],
            )
        ],
        citations=[Source(title="Official Source", url="https://example.com/source")],
    )


def test_init_db_idempotent(tmp_path):
    """Calling init_db multiple times must not raise errors."""
    db_file = str(tmp_path / "test.db")
    init_db(db_path=db_file)
    init_db(db_path=db_file)  # Second invocation should succeed idempotently


def test_save_and_get_analysis(tmp_path):
    """Test saving an analysis and retrieving it with parsed Pydantic model."""
    db_file = str(tmp_path / "test.db")
    init_db(db_path=db_file)

    sample_result = _make_dummy_result("Chandrayaan-3 Lands on Moon", "Real")
    row_id = save_analysis(
        input_type="text",
        headline="Chandrayaan-3 Lands on Moon",
        source_url="https://isro.gov.in",
        result=sample_result,
        db_path=db_file,
    )
    assert isinstance(row_id, int)
    assert row_id > 0

    record = get_analysis(row_id, db_path=db_file)
    assert record is not None
    assert record["id"] == row_id
    assert record["headline"] == "Chandrayaan-3 Lands on Moon"
    assert record["source_url"] == "https://isro.gov.in"
    assert record["verdict"] == "Real"
    assert record["confidence"] == 92
    assert record["credibility"] == 85

    # Check that result was parsed back into an AnalysisResult
    assert isinstance(record["result"], AnalysisResult)
    assert record["result"].verdict == "Real"
    assert len(record["result"].claim_results) == 1
    assert record["result"].claim_results[0].claim == "Claim A"


def test_list_history(tmp_path):
    """Test listing historical items sorted by newest first."""
    db_file = str(tmp_path / "test.db")
    init_db(db_path=db_file)

    id1 = save_analysis("text", "Story 1", None, _make_dummy_result("Story 1"), db_path=db_file)
    id2 = save_analysis("url", "Story 2", "https://news.com", _make_dummy_result("Story 2"), db_path=db_file)

    history = list_history(limit=10, db_path=db_file)
    assert len(history) == 2
    # Newest item first (id2 then id1)
    assert history[0]["id"] == id2
    assert history[0]["headline"] == "Story 2"
    assert history[1]["id"] == id1

    # Check limit param
    limited = list_history(limit=1, db_path=db_file)
    assert len(limited) == 1
    assert limited[0]["id"] == id2


def test_delete_analysis(tmp_path):
    """Test deleting an analysis record."""
    db_file = str(tmp_path / "test.db")
    init_db(db_path=db_file)

    row_id = save_analysis("text", "To Delete", None, _make_dummy_result("To Delete"), db_path=db_file)
    assert get_analysis(row_id, db_path=db_file) is not None

    deleted = delete_analysis(row_id, db_path=db_file)
    assert deleted is True

    # Record should be gone
    assert get_analysis(row_id, db_path=db_file) is None

    # Deleting nonexistent ID returns False
    assert delete_analysis(99999, db_path=db_file) is False

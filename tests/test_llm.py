"""Unit tests for core/llm.py error handling and schema validation."""

from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from core.llm import LLMError, generate_structured


class DummyOutput(BaseModel):
    summary: str
    score: int = Field(ge=0, le=100)


def test_llm_empty_response_raises_llm_error():
    """An empty text response must raise LLMError, not an unhandled exception."""
    mock_response = MagicMock()
    mock_response.text = ""

    with patch("core.llm.client.models.generate_content", return_value=mock_response):
        with pytest.raises(LLMError) as exc_info:
            generate_structured("Say something", DummyOutput, max_retries=1, initial_backoff=0.01)
        assert "empty response" in str(exc_info.value).lower() or "failed after" in str(exc_info.value).lower()


def test_llm_malformed_json_raises_llm_error():
    """Invalid JSON response must raise LLMError, not raw JSONDecodeError."""
    mock_response = MagicMock()
    mock_response.text = "{ not valid json }"

    with patch("core.llm.client.models.generate_content", return_value=mock_response):
        with pytest.raises(LLMError) as exc_info:
            generate_structured("Say something", DummyOutput, max_retries=1, initial_backoff=0.01)
        assert "structured generation failed" in str(exc_info.value).lower()


def test_llm_schema_violation_raises_llm_error():
    """Out-of-range fields violating Pydantic schema must raise LLMError."""
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Test", "score": 999}'  # score > 100 violates Field(le=100)

    with patch("core.llm.client.models.generate_content", return_value=mock_response):
        with pytest.raises(LLMError):
            generate_structured("Say something", DummyOutput, max_retries=0)


def test_llm_successful_mock():
    """Valid structured response returns properly typed Pydantic object."""
    mock_response = MagicMock()
    mock_response.text = '{"summary": "All good", "score": 95}'

    with patch("core.llm.client.models.generate_content", return_value=mock_response):
        result = generate_structured("Prompt", DummyOutput, max_retries=0)
        assert isinstance(result, DummyOutput)
        assert result.summary == "All good"
        assert result.score == 95

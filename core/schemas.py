"""Pydantic models and data contracts for TruthLens."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class TextAnalysis(BaseModel):
    """Result of textual analysis including clickbait and claim extraction."""

    clickbait_score: int = Field(ge=0, le=100)  # 100 = extreme clickbait
    sensationalism_score: int = Field(ge=0, le=100)
    headline_body_consistency: int = Field(ge=0, le=100)  # 100 = fully consistent
    key_claims: list[str]  # max 3 verifiable claims
    reasoning: str


class ImageAnalysis(BaseModel):
    """Result of multimodal image-context verification."""

    manipulation_suspicion: int = Field(ge=0, le=100)
    context_match: int = Field(ge=0, le=100)  # 100 = image fits the story
    verdict: Literal["Consistent", "Possible Mismatch", "Likely Manipulated"]
    reasoning: str


class Source(BaseModel):
    """Web source citation and stance for claim verification."""

    title: str
    url: str
    snippet: str = ""
    stance: Literal["supports", "contradicts", "neutral"] = "neutral"


class ClaimResult(BaseModel):
    """Verification result for a single claim with supporting/refuting sources."""

    claim: str
    status: Literal["Supported", "Contradicted", "Unverified"]
    reasoning: str
    sources: list[Source] = []


class AnalysisResult(BaseModel):
    """Aggregated analysis verdict, confidence, and evidence."""

    verdict: Literal["Real", "Misleading", "Fake"]
    confidence: int = Field(ge=0, le=100)
    credibility_score: int = Field(ge=0, le=100)
    explanation: str
    text_analysis: TextAnalysis
    image_analysis: Optional[ImageAnalysis] = None
    claim_results: list[ClaimResult]
    citations: list[Source]

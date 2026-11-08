"""Pipeline orchestrator coordinating text analysis, multimodal verification, scoring, and storage."""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from core.db import save_analysis
from core.image_analysis import analyze_image
from core.retrieval import fetch_article
from core.schemas import AnalysisResult, ClaimResult, ImageAnalysis, Source, TextAnalysis
from core.scoring import (
    compute_claim_score,
    compute_confidence,
    compute_credibility,
    determine_verdict,
    generate_explanation,
)
from core.text_analysis import analyze_text


def run_analysis(
    url: Optional[str] = None,
    headline: Optional[str] = None,
    body: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    db_path: Optional[str] = None,
) -> AnalysisResult:
    """Run end-to-end news authenticity and clickbait classification.

    Args:
        url: Optional URL to fetch news article from.
        headline: News headline (required if url is not provided).
        body: Optional full text of the news story.
        image_bytes: Optional raw image bytes for vision analysis.
        progress_callback: Optional callable for UI progress status updates.
        db_path: Optional SQLite database file path override.

    Returns:
        Populated and persisted AnalysisResult instance.

    Raises:
        ValueError: If neither URL nor headline is supplied, or URL fetch yields no content.
    """

    def notify(step_msg: str) -> None:
        if progress_callback:
            try:
                progress_callback(step_msg)
            except Exception:
                pass

    # 1. Validation & Input Normalization
    clean_url = (url or "").strip()
    clean_headline = (headline or "").strip()
    clean_body = (body or "").strip()

    if not clean_url and not clean_headline:
        raise ValueError("Please provide either a news URL or a headline to analyze.")

    input_type = "url" if clean_url else ("text+image" if image_bytes else "text")

    if clean_url:
        notify("Reading article from URL...")
        fetched_title, fetched_body = fetch_article(clean_url)
        if not clean_headline and fetched_title:
            clean_headline = fetched_title
        if not clean_body and fetched_body:
            clean_body = fetched_body

        if not clean_headline:
            raise ValueError(
                "Could not extract article title from the provided URL. Please paste the headline directly."
            )

    # 2. Text Analysis
    notify("Analyzing headline, clickbait signals, and extracting claims...")
    text_analysis = analyze_text(headline=clean_headline, body=clean_body)

    # 3. Parallel Image Analysis and Claim Verification
    notify("Verifying claims and inspecting image...")
    claim_results: list[ClaimResult] = []
    image_analysis: Optional[ImageAnalysis] = None

    def _run_claims_verification() -> list[ClaimResult]:
        from core.verification import verify_claims_parallel

        claims = text_analysis.key_claims
        if not claims:
            # Headline-only fallback query if no distinct claims were parsed
            claims = [clean_headline]
        return verify_claims_parallel(claims, max_workers=3)

    def _run_image_analysis() -> Optional[ImageAnalysis]:
        if not image_bytes:
            return None
        try:
            return analyze_image(
                image_bytes=image_bytes,
                headline=clean_headline,
                body_summary=clean_body[:500] if clean_body else None,
            )
        except Exception:
            # Partial failure policy: continue without image analysis if it fails
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims_future = executor.submit(_run_claims_verification)
        image_future = executor.submit(_run_image_analysis)

        try:
            claim_results = claims_future.result()
        except Exception:
            # Fallback if claim verification fails
            claim_results = [
                ClaimResult(
                    claim=clean_headline,
                    status="Unverified",
                    reasoning="Verification failed due to connectivity or query error.",
                    sources=[],
                )
            ]

        try:
            image_analysis = image_future.result()
        except Exception:
            image_analysis = None

    # 4. Citations extraction & deduplication
    citations: list[Source] = []
    seen_urls: set[str] = set()
    for cr in claim_results:
        for src in cr.sources:
            if src.url and src.url not in seen_urls:
                citations.append(src)
                seen_urls.add(src.url)

    # 5. Scoring & Verdict Aggregation
    notify("Computing credibility score, confidence, and verdict...")
    claim_score = compute_claim_score(claim_results)
    image_manipulation = image_analysis.manipulation_suspicion if image_analysis else None
    credibility = compute_credibility(
        claim_score=claim_score,
        consistency=text_analysis.headline_body_consistency,
        clickbait_score=text_analysis.clickbait_score,
        image_manipulation=image_manipulation,
    )
    verdict = determine_verdict(
        credibility=credibility,
        clickbait_score=text_analysis.clickbait_score,
        consistency=text_analysis.headline_body_consistency,
        claim_results=claim_results,
    )
    confidence = compute_confidence(
        credibility=credibility,
        claim_results=claim_results,
        total_sources_count=len(citations),
    )

    # 6. Explanation
    notify("Synthesizing final explanation...")
    explanation = generate_explanation(
        headline=clean_headline,
        verdict=verdict,
        credibility=credibility,
        confidence=confidence,
        text_analysis=text_analysis,
        claim_results=claim_results,
        citations=citations,
        image_analysis=image_analysis,
    )

    # 7. Persist to SQLite Database
    analysis_result = AnalysisResult(
        verdict=verdict,
        confidence=confidence,
        credibility_score=credibility,
        explanation=explanation,
        text_analysis=text_analysis,
        image_analysis=image_analysis,
        claim_results=claim_results,
        citations=citations,
    )

    try:
        save_analysis(
            input_type=input_type,
            headline=clean_headline,
            source_url=clean_url if clean_url else None,
            result=analysis_result,
            db_path=db_path,
        )
    except Exception:
        # Saving history is secondary to returning result
        pass

    notify("Analysis complete!")
    return analysis_result

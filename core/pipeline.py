"""Pipeline orchestrator coordinating text analysis, multimodal reverse search, scoring, and storage."""

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
    """Run news authenticity and deep-dive reverse image analysis.

    Supports:
    - Text only (headline + optional body)
    - URL only (extracts title & body)
    - Headline + Image (cross-modal consistency and claim verification)
    - Image only (autonomous deep-dive reverse search, entity detection & origin check)

    Args:
        url: Optional URL to fetch news article from.
        headline: News headline (optional if image or url is provided).
        body: Optional full text of the news story.
        image_bytes: Optional raw image bytes for vision analysis / reverse search.
        progress_callback: Optional callable for UI progress status updates.
        db_path: Optional SQLite database file path override.

    Returns:
        Populated and persisted AnalysisResult instance.

    Raises:
        ValueError: If neither URL, headline, nor image is supplied.
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

    if not clean_url and not clean_headline and not image_bytes:
        raise ValueError("Please provide an image, a news URL, or a headline to analyze.")

    # Determine execution flow
    if clean_url:
        input_type = "url"
    elif clean_headline and image_bytes:
        input_type = "text+image"
    elif image_bytes:
        input_type = "image_only"
    else:
        input_type = "text"

    # URL Ingestion
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

    # 2. Execution path for IMAGE-ONLY mode (Deep Dive Reverse Search)
    if input_type == "image_only":
        notify("Inspecting image, recognizing visual entities, and formulating reverse queries...")
        image_analysis = analyze_image(image_bytes=image_bytes, headline=None, body_summary=None)
        if not image_analysis:
            raise ValueError("Unable to read or inspect the uploaded image.")

        # Inferred topic / context
        inferred_subject = (
            image_analysis.origin_context
            or (", ".join(image_analysis.detected_entities[:3]) if image_analysis.detected_entities else "")
            or "Visual Media Investigation"
        )
        clean_headline = f"Reverse Image Deep Dive: {inferred_subject}"

        notify("Performing deep dive reverse search across web records...")
        reverse_queries = list(image_analysis.reverse_search_queries)
        if not reverse_queries:
            reverse_queries = [inferred_subject]

        from core.verification import verify_claims_parallel

        claim_results = verify_claims_parallel(reverse_queries[:3], max_workers=3)

        # Synthesize equivalent TextAnalysis representation
        text_analysis = TextAnalysis(
            clickbait_score=0,
            sensationalism_score=image_analysis.manipulation_suspicion,
            headline_body_consistency=image_analysis.context_match,
            key_claims=reverse_queries[:3],
            reasoning=(
                f"Autonomous reverse search conducted on image. "
                f"Entities detected: {', '.join(image_analysis.detected_entities) if image_analysis.detected_entities else 'None'}. "
                f"Origin context: {image_analysis.origin_context or 'Unspecified'}."
            ),
        )

    else:
        # Standard Text / URL / Text+Image flow
        notify("Analyzing headline, clickbait signals, and extracting claims...")
        text_analysis = analyze_text(headline=clean_headline, body=clean_body)

        notify("Verifying claims and inspecting image...")
        claim_results: list[ClaimResult] = []
        image_analysis: Optional[ImageAnalysis] = None

        def _run_claims_verification() -> list[ClaimResult]:
            from core.verification import verify_claims_parallel

            claims = list(text_analysis.key_claims)
            if not claims:
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
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            claims_future = executor.submit(_run_claims_verification)
            image_future = executor.submit(_run_image_analysis)

            try:
                claim_results = claims_future.result()
            except Exception:
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

        # If image analysis produced reverse search queries, run reverse search on them too
        if image_analysis and image_analysis.reverse_search_queries:
            notify("Cross-referencing reverse image search records...")
            from core.verification import verify_claims_parallel

            img_claims = verify_claims_parallel(image_analysis.reverse_search_queries[:2], max_workers=2)
            # Append non-duplicate claim results
            existing_claims = {cr.claim for cr in claim_results}
            for ic in img_claims:
                if ic.claim not in existing_claims:
                    claim_results.append(ic)
                    existing_claims.add(ic.claim)

    # 3. Citations extraction & deduplication
    citations: list[Source] = []
    seen_urls: set[str] = set()
    for cr in claim_results:
        for src in cr.sources:
            if src.url and src.url not in seen_urls:
                citations.append(src)
                seen_urls.add(src.url)

    # 4. Scoring & Verdict Aggregation
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

    # If image alone was judged, enforce appropriate verdict
    if input_type == "image_only" and image_analysis:
        if image_analysis.verdict == "Likely Manipulated":
            verdict = "Fake"
        elif image_analysis.verdict == "Possible Mismatch":
            verdict = "Misleading"
        elif image_analysis.verdict == "Consistent":
            verdict = "Real"
            credibility = max(credibility, 85)

    confidence = compute_confidence(
        credibility=credibility,
        claim_results=claim_results,
        total_sources_count=len(citations),
    )

    # 5. Explanation Synthesis
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

    # 6. Persist to SQLite Database
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
        pass

    notify("Analysis complete!")
    return analysis_result

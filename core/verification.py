"""Claim verification engine evaluating retrieved web sources against claims."""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from core.llm import generate_structured
from core.retrieval import search_web
from core.schemas import ClaimResult, Source


def verify_claim(claim: str, max_sources: int = 5) -> ClaimResult:
    """Verify a single factual claim by retrieving evidence and querying Gemini.

    Args:
        claim: The factual claim to verify.
        max_sources: Maximum search evidence snippets to retrieve.

    Returns:
        ClaimResult indicating Supported, Contradicted, or Unverified with citations.
    """
    clean_claim = (claim or "").strip()
    if not clean_claim:
        return ClaimResult(
            claim="",
            status="Unverified",
            reasoning="Empty claim provided.",
            sources=[],
        )

    # 1. Retrieve web evidence
    retrieved_sources = search_web(clean_claim, max_results=max_sources)
    if not retrieved_sources:
        return ClaimResult(
            claim=clean_claim,
            status="Unverified",
            reasoning="No relevant web search results or evidence could be retrieved to verify this claim.",
            sources=[],
        )

    # Create allowed URL lookup for strict citation integrity
    allowed_sources_by_url = {s.url.strip(): s for s in retrieved_sources if s.url}

    sources_text_block = "\n".join(
        f"[{i+1}] Title: {src.title}\n    URL: {src.url}\n    Snippet: {src.snippet}"
        for i, src in enumerate(retrieved_sources)
    )

    prompt = f"""You are an objective, strict fact-checking judge. Verify the given claim ONLY using the evidence snippets below.

CLAIM: {clean_claim}

RETRIEVED WEB EVIDENCE:
{sources_text_block}

STRICT FACT-CHECKING RULES:
1. Judge ONLY from the provided snippets above. Do NOT use outside knowledge or assumptions to fill gaps.
2. If the snippets directly confirm the claim with clear factual reporting, status is "Supported".
3. If the snippets directly refute or debunk the claim, status is "Contradicted".
4. If the snippets are inconclusive, irrelevant, off-topic, or lack explicit confirmation, status MUST be "Unverified".
5. For each source, specify its stance: "supports", "contradicts", or "neutral".
6. DO NOT invent URLs. Every citation must be one of the retrieved URLs listed above.

Return ONLY JSON matching the ClaimResult schema:
- claim: the claim text
- status: "Supported", "Contradicted", or "Unverified"
- reasoning: 1-2 concise sentences explaining the evidence verdict
- sources: list of sources from the evidence snippets with their stance
"""

    llm_result: ClaimResult = generate_structured(prompt=prompt, schema=ClaimResult, temperature=0.1)

    # Enforce URL integrity: discard any hallucinated URL not present in retrieved_sources
    verified_sources: list[Source] = []
    seen_urls: set[str] = set()

    for item in llm_result.sources:
        url_clean = (item.url or "").strip()
        if url_clean in allowed_sources_by_url and url_clean not in seen_urls:
            original_src = allowed_sources_by_url[url_clean]
            verified_sources.append(
                Source(
                    title=original_src.title,
                    url=url_clean,
                    snippet=original_src.snippet,
                    stance=item.stance,
                )
            )
            seen_urls.add(url_clean)

    # If model did not emit the sources list or emitted invalid URLs, use retrieved sources with neutral stance
    if not verified_sources:
        verified_sources = retrieved_sources

    return ClaimResult(
        claim=clean_claim,
        status=llm_result.status,
        reasoning=llm_result.reasoning,
        sources=verified_sources,
    )


def verify_claims_parallel(claims: list[str], max_workers: int = 3) -> list[ClaimResult]:
    """Verify multiple claims concurrently using a thread pool to minimize latency."""
    valid_claims = [c.strip() for c in claims if c and c.strip()]
    if not valid_claims:
        return []

    workers = min(len(valid_claims), max_workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(verify_claim, valid_claims))

    return results

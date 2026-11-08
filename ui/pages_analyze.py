"""Streamlit Analyze Page for TruthLens with Unified Multimodal & Image-Only Deep Dive."""

import time
import streamlit as st

from core.pipeline import run_analysis
from core.schemas import AnalysisResult
from ui.components import (
    render_citations_list,
    render_claim_results,
    render_disclaimer,
    render_image_verdict,
    render_scores,
    render_verdict_badge,
)

RATE_LIMIT_COOLDOWN_SECONDS = 3.0


def render_analyze_page() -> None:
    """Render the primary investigation interface supporting any combination of Image, Headline, and URL."""
    st.header("🔎 TruthLens Investigation Engine")
    st.write(
        "Investigate media authenticity: **upload an image** to run an autonomous deep-dive reverse search, "
        "or enter a **headline** or **article URL** to verify claims and detect clickbait."
    )

    col_input1, col_input2 = st.columns([1, 1], gap="medium")

    with col_input1:
        st.subheader("📰 Story & Source Details (Optional)")
        url = st.text_input(
            "News Article URL (Optional)",
            placeholder="https://www.bbc.com/news/article-12345",
            help="Paste a link to automatically scrape the article headline and body text.",
            key="input_url",
        )
        headline = st.text_input(
            "News Headline (Optional)",
            placeholder="e.g. Breaking news claim or leave empty to analyze story body / image...",
            help="The main claim or headline to fact-check. Can be left empty if providing story text, image, or URL.",
            key="input_headline",
        )
        body = st.text_area(
            "Story Text / Body (Optional)",
            placeholder="Paste full article text, breaking story paragraphs, or claims to investigate...",
            height=110,
            help="Paste story text, paragraphs, or claims. TruthLens will extract and verify factual claims from this text.",
            key="input_body",
        )

    with col_input2:
        st.subheader("🖼️ Associated Image / Media (Optional)")
        uploaded_img = st.file_uploader(
            "Upload story image (JPG, PNG, WEBP, max 5 MB)",
            type=["jpg", "jpeg", "png", "webp"],
            help="Upload any photograph, screenshot, or artwork. If provided alone without a headline, TruthLens executes an autonomous reverse-search to uncover origins and background info.",
            key="input_image",
        )

        image_bytes = None
        if uploaded_img:
            image_bytes = uploaded_img.getvalue()
            st.image(image_bytes, caption="Uploaded Image Preview", width=340)

    # Contextual mode indicators
    has_image = image_bytes is not None
    has_headline = bool(headline and headline.strip())
    has_body = bool(body and body.strip())
    has_url = bool(url and url.strip())

    if has_image and not has_headline and not has_body and not has_url:
        st.info(
            "💡 **Autonomous Reverse Image Search Mode Active**\n\n"
            "No story text, headline, or URL entered. TruthLens will inspect this image, identify visual entities, "
            "reverse-search web records, and uncover the background origin and history of this media."
        )
    elif has_body and not has_headline and not has_url and not has_image:
        st.info(
            "💡 **Story Fact-Check Mode Active**\n\n"
            "TruthLens will analyze the story text, extract key claims, and verify them against real-time web evidence."
        )

    st.markdown("")
    btn_analyze = st.button("🔍 Analyze Authenticity", type="primary", use_container_width=True)

    if btn_analyze:

        if not has_image and not has_headline and not has_body and not has_url:
            st.error("Please provide story text, a news headline, an article URL, or an image before analyzing.")
            return

        now = time.time()
        last_run = st.session_state.get("last_analysis_time", 0.0)
        if now - last_run < RATE_LIMIT_COOLDOWN_SECONDS:
            st.warning("Please wait a few seconds between requests to protect API limits.")
            return

        st.session_state["last_analysis_time"] = now

        # Dynamic progress description
        if has_image and not has_headline and not has_body and not has_url:
            investigation_title = "Performing deep-dive reverse image search on media..."
        elif has_body and not has_headline and not has_url and not has_image:
            investigation_title = "Analyzing story text, extracting claims, and verifying against web evidence..."
        elif has_image and (has_headline or has_body):
            investigation_title = "Verifying multimodal story and media consistency..."
        elif has_url:
            investigation_title = "Fetching article and verifying claims against web evidence..."
        else:
            investigation_title = "Analyzing headline credibility and extracting claims..."

        with st.status(investigation_title, expanded=True) as status_box:
            try:
                def update_progress(msg: str):
                    status_box.write(f"• {msg}")

                result: AnalysisResult = run_analysis(
                    url=url.strip() if url else None,
                    headline=headline.strip() if headline else None,
                    body=body.strip() if body else None,
                    image_bytes=image_bytes,
                    progress_callback=update_progress,
                )
                status_box.update(label="Investigation complete!", state="complete", expanded=False)
                st.session_state["current_analysis"] = result
            except Exception as err:
                status_box.update(label="Investigation failed", state="error", expanded=True)
                st.error(f"Analysis Error: {err}")
                return

    # --- RESULTS DASHBOARD ---
    if "current_analysis" in st.session_state and st.session_state["current_analysis"]:
        result: AnalysisResult = st.session_state["current_analysis"]
        st.markdown("---")
        render_verdict_badge(result.verdict)
        render_scores(
            credibility_score=result.credibility_score,
            confidence=result.confidence,
            clickbait_score=result.text_analysis.clickbait_score,
        )

        st.subheader("💡 Investigation Summary & Background Information")
        st.write(result.explanation)

        if result.image_analysis:
            st.markdown("---")
            render_image_verdict(result.image_analysis)

        st.markdown("---")
        render_claim_results(result.claim_results)

        st.markdown("---")
        render_citations_list(result.citations)

        st.markdown("---")
        render_disclaimer()

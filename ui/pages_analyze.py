"""Streamlit Analyze Page for TruthLens."""

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
    """Render the primary news analysis interface."""
    st.header("🔎 Analyze News Authenticity")
    st.write(
        "Enter a news article URL or paste a headline and body text to inspect credibility, "
        "clickbait characteristics, and claim veracity."
    )

    # Input Mode Tabs
    tab_text, tab_url = st.tabs(["📝 Headline & Text", "🔗 News Article URL"])

    headline = ""
    body = ""
    url = ""

    with tab_text:
        headline = st.text_input(
            "Headline *",
            placeholder="e.g. NASA confirms discovery of liquid water on Mars",
            key="input_headline",
        )
        body = st.text_area(
            "Body Text (Optional)",
            placeholder="Paste article body paragraphs here for consistency and deep claim extraction...",
            height=150,
            key="input_body",
        )

    with tab_url:
        url = st.text_input(
            "Article URL *",
            placeholder="https://example.com/news/article-headline",
            key="input_url",
        )
        st.caption("TruthLens will fetch the article title, body paragraphs, and evaluate the claims.")

    # Image Upload Section
    st.subheader("🖼️ Associated Image (Optional)")
    uploaded_image = st.file_uploader(
        "Upload story image (JPG, PNG, WEBP, max 5 MB)",
        type=["jpg", "jpeg", "png", "webp"],
        key="image_uploader",
    )
    image_bytes = None
    if uploaded_image:
        image_bytes = uploaded_image.getvalue()
        st.image(image_bytes, caption="Uploaded Image Preview", width=360)

    # Submission Action
    analyze_btn = st.button("🔍 Analyze Authenticity", type="primary", use_container_width=True)

    if analyze_btn:
        # Rate limit cooldown check
        now = time.time()
        last_run = st.session_state.get("last_analysis_time", 0.0)
        if now - last_run < RATE_LIMIT_COOLDOWN_SECONDS:
            st.warning("Please wait a few seconds between analyses to protect free API limits.")
            return

        # Basic client validation
        has_headline = bool(headline and headline.strip())
        has_url = bool(url and url.strip())

        if not has_headline and not has_url:
            st.error("Please provide either a headline or a news URL before analyzing.")
            return

        st.session_state["last_analysis_time"] = now

        # Execute analysis pipeline with real-time status updates
        with st.status("Analyzing news story...", expanded=True) as status_box:
            try:
                def update_progress(msg: str):
                    status_box.write(f"• {msg}")

                result: AnalysisResult = run_analysis(
                    url=url if has_url else None,
                    headline=headline if has_headline else None,
                    body=body,
                    image_bytes=image_bytes,
                    progress_callback=update_progress,
                )
                status_box.update(label="Analysis complete!", state="complete", expanded=False)
                st.session_state["current_analysis"] = result
                st.session_state["analyzed_headline"] = headline or (result.citations[0].title if result.citations else "Analyzed Story")
            except Exception as err:
                status_box.update(label="Analysis failed", state="error", expanded=True)
                st.error(f"Analysis Error: {err}")
                return

    # Render persisted analysis result from session state
    if "current_analysis" in st.session_state and st.session_state["current_analysis"]:
        result: AnalysisResult = st.session_state["current_analysis"]
        st.markdown("---")
        render_verdict_badge(result.verdict)
        render_scores(
            credibility_score=result.credibility_score,
            confidence=result.confidence,
            clickbait_score=result.text_analysis.clickbait_score,
        )

        st.subheader("💡 Summary & Evidence Explanation")
        st.write(result.explanation)

        col_text1, col_text2 = st.columns(2)
        with col_text1:
            st.markdown(f"**Headline-Body Consistency:** {result.text_analysis.headline_body_consistency}%")
        with col_text2:
            st.markdown(f"**Sensationalism Score:** {result.text_analysis.sensationalism_score}%")
        st.caption(f"Text Analysis Reasoning: {result.text_analysis.reasoning}")

        if result.image_analysis:
            st.markdown("---")
            render_image_verdict(result.image_analysis)

        st.markdown("---")
        render_claim_results(result.claim_results)

        st.markdown("---")
        render_citations_list(result.citations)

        st.markdown("---")
        render_disclaimer()

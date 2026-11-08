"""Streamlit Analyze Page for TruthLens with Deep Dive Reverse Image Search."""

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
    """Render the primary news and reverse image analysis interface."""
    st.header("🔎 TruthLens Investigation Engine")
    st.write(
        "Verify online news authenticity, detect clickbait, or upload an image to run an "
        "autonomous deep-dive reverse search to discover its true origin and context."
    )

    # Input Mode Tabs
    tab_img, tab_text, tab_url = st.tabs(
        ["🖼️ Image Deep Dive", "📝 Headline & Text", "🔗 News Article URL"]
    )

    headline = ""
    body = ""
    url = ""
    image_bytes = None

    with tab_img:
        st.write("Upload an image alone to perform an automated visual forensic and reverse-search investigation.")
        uploaded_img_standalone = st.file_uploader(
            "Upload Image for Deep Dive (JPG, PNG, WEBP, max 5 MB)",
            type=["jpg", "jpeg", "png", "webp"],
            key="standalone_image_uploader",
        )
        optional_context = st.text_input(
            "Optional Context / Claim (Leave blank to search purely by image)",
            placeholder="e.g. Claimed to be taken in Paris yesterday",
            key="img_optional_headline",
        )
        if uploaded_img_standalone:
            image_bytes = uploaded_img_standalone.getvalue()
            st.image(image_bytes, caption="Uploaded Image for Reverse Investigation", width=420)
        if optional_context and optional_context.strip():
            headline = optional_context.strip()

    with tab_text:
        text_headline = st.text_input(
            "Headline",
            placeholder="e.g. NASA confirms discovery of liquid water on Mars",
            key="input_headline",
        )
        text_body = st.text_area(
            "Body Text (Optional)",
            placeholder="Paste article body paragraphs here for consistency and deep claim extraction...",
            height=130,
            key="input_body",
        )
        uploaded_text_img = st.file_uploader(
            "Attach story image (Optional)",
            type=["jpg", "jpeg", "png", "webp"],
            key="text_tab_image_uploader",
        )
        if uploaded_text_img and not image_bytes:
            image_bytes = uploaded_text_img.getvalue()
            st.image(image_bytes, caption="Attached Image", width=360)
        if text_headline and text_headline.strip():
            headline = text_headline.strip()
            body = text_body.strip() if text_body else ""

    with tab_url:
        input_url = st.text_input(
            "Article URL",
            placeholder="https://example.com/news/article-headline",
            key="input_url",
        )
        st.caption("TruthLens will fetch the article title, body paragraphs, and evaluate the claims.")
        uploaded_url_img = st.file_uploader(
            "Attach story image (Optional)",
            type=["jpg", "jpeg", "png", "webp"],
            key="url_tab_image_uploader",
        )
        if uploaded_url_img and not image_bytes:
            image_bytes = uploaded_url_img.getvalue()
            st.image(image_bytes, caption="Attached Image", width=360)
        if input_url and input_url.strip():
            url = input_url.strip()

    # Submission Action
    st.markdown("")
    analyze_btn = st.button("🔍 Run Analysis / Deep Dive", type="primary", use_container_width=True)

    if analyze_btn:
        # Rate limit cooldown check
        now = time.time()
        last_run = st.session_state.get("last_analysis_time", 0.0)
        if now - last_run < RATE_LIMIT_COOLDOWN_SECONDS:
            st.warning("Please wait a few seconds between analyses to protect API quotas.")
            return

        has_headline = bool(headline and headline.strip())
        has_url = bool(url and url.strip())
        has_image = bool(image_bytes is not None and len(image_bytes) > 0)

        if not has_headline and not has_url and not has_image:
            st.error("Please upload an image, enter a headline, or paste a news URL to analyze.")
            return

        st.session_state["last_analysis_time"] = now

        status_label = (
            "Performing deep-dive reverse image investigation..."
            if (has_image and not has_headline and not has_url)
            else "Analyzing news authenticity..."
        )

        with st.status(status_label, expanded=True) as status_box:
            try:
                def update_progress(msg: str):
                    status_box.write(f"• {msg}")

                result: AnalysisResult = run_analysis(
                    url=url if has_url else None,
                    headline=headline if has_headline else None,
                    body=body if body else None,
                    image_bytes=image_bytes,
                    progress_callback=update_progress,
                )
                status_box.update(label="Investigation complete!", state="complete", expanded=False)
                st.session_state["current_analysis"] = result
            except Exception as err:
                status_box.update(label="Investigation failed", state="error", expanded=True)
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

        if result.image_analysis:
            st.markdown("---")
            render_image_verdict(result.image_analysis)

        st.markdown("---")
        render_claim_results(result.claim_results)

        st.markdown("---")
        render_citations_list(result.citations)

        st.markdown("---")
        render_disclaimer()

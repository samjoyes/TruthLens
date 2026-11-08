"""Reusable Streamlit UI components: verdict badges, gauges, claims, and citations."""

import streamlit as st
from typing import Optional
from core.schemas import AnalysisResult, ClaimResult, ImageAnalysis, Source


def render_disclaimer() -> None:
    """Render the standard TruthLens analytical disclaimer."""
    st.info(
        "ℹ️ **Disclaimer:** TruthLens provides an AI-assisted estimate, not a final judgement. "
        "Always check the cited sources."
    )


def render_verdict_badge(verdict: str) -> None:
    """Render an eye-catching, color-coded verdict banner."""
    color_map = {
        "Real": {"bg": "#d4edda", "border": "#28a745", "text": "#155724", "icon": "✅"},
        "Misleading": {"bg": "#fff3cd", "border": "#ffc107", "text": "#856404", "icon": "⚠️"},
        "Fake": {"bg": "#f8d7da", "border": "#dc3545", "text": "#721c24", "icon": "🚨"},
    }
    style = color_map.get(verdict, color_map["Misleading"])

    badge_html = f"""
    <div style="
        background-color: {style['bg']};
        border: 2px solid {style['border']};
        color: {style['text']};
        padding: 14px 20px;
        border-radius: 8px;
        font-size: 1.4rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    ">
        {style['icon']} Verdict: {verdict.upper()}
    </div>
    """
    st.markdown(badge_html, unsafe_allow_html=True)


def render_scores(credibility_score: int, confidence: int, clickbait_score: int) -> None:
    """Render key metrics in columns."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Credibility Score",
            value=f"{credibility_score}%",
            help="Weighted score from claim verification, text consistency, clickbait detection, and image analysis.",
        )
        st.progress(credibility_score / 100.0)
    with col2:
        st.metric(
            label="Confidence",
            value=f"{confidence}%",
            help="Certainty margin based on source consistency and evidence availability.",
        )
        st.progress(confidence / 100.0)
    with col3:
        st.metric(
            label="Clickbait Level",
            value=f"{clickbait_score}%",
            help="Measured sensationalism and curiosity gap heuristics.",
        )
        st.progress(clickbait_score / 100.0)


def render_image_verdict(image_analysis: Optional[ImageAnalysis]) -> None:
    """Render the image verification card if an image was analyzed."""
    if not image_analysis:
        return

    st.subheader("🖼️ Multimodal Image Analysis")
    verdict_colors = {
        "Consistent": "green",
        "Possible Mismatch": "orange",
        "Likely Manipulated": "red",
    }
    v_color = verdict_colors.get(image_analysis.verdict, "gray")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Image Verdict:** :{v_color}[{image_analysis.verdict}]")
        st.write(f"• **Context Match:** {image_analysis.context_match}%")
        st.write(f"• **Manipulation Suspicion:** {image_analysis.manipulation_suspicion}%")
    with col2:
        st.markdown("**Visual Assessment Reasoning:**")
        st.caption(image_analysis.reasoning)


def render_claim_results(claim_results: list[ClaimResult]) -> None:
    """Render expandable breakdown for each extracted claim."""
    st.subheader("🔍 Claim Verification Breakdown")
    if not claim_results:
        st.caption("No specific verifiable factual claims were extracted.")
        return

    status_icons = {
        "Supported": "🟢 Supported",
        "Contradicted": "🔴 Contradicted",
        "Unverified": "⚪ Unverified",
    }

    for i, cr in enumerate(claim_results, 1):
        status_label = status_icons.get(cr.status, cr.status)
        with st.expander(f"Claim {i}: {cr.claim} ({status_label})", expanded=(i == 1)):
            st.write(f"**Status:** {status_label}")
            st.write(f"**Evidence Reasoning:** {cr.reasoning}")
            if cr.sources:
                st.markdown("**Supporting/Contradicting Sources for this claim:**")
                for s in cr.sources:
                    stance_pill = (
                        "✅ Supports"
                        if s.stance == "supports"
                        else ("❌ Contradicts" if s.stance == "contradicts" else "⚪ Neutral")
                    )
                    st.markdown(f"- [{s.title}]({s.url}) — *{stance_pill}*")
                    if s.snippet:
                        st.caption(f"> {s.snippet}")


def render_citations_list(citations: list[Source]) -> None:
    """Render the verified list of retrieved citations with clickable links."""
    st.subheader("📚 Source Citations")
    if not citations:
        st.caption("No external sources were retrieved for this query.")
        return

    for idx, src in enumerate(citations, 1):
        st.markdown(f"**[{idx}] [{src.title}]({src.url})**")
        if src.snippet:
            st.caption(f'"{src.snippet}"')

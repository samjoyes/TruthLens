"""Streamlit About Page with system architecture, limitations, and project credits."""

import streamlit as st


def render_about_page() -> None:
    """Render project description, architecture details, and academic credits."""
    st.header("ℹ️ About TruthLens")
    st.markdown(
        """
        **TruthLens** is an automated credibility and clickbait classification system engineered to analyze
        online news articles using multimodal Vision-Language Models (Gemini) and real-time live web retrieval.
        """
    )

    st.subheader("🛠️ How It Works (Pipeline Architecture)")
    st.markdown(
        """
        1. **Input Normalization & Extraction**:
           Accepts either direct text (headline and body) or a news URL. When given a URL, it securely extracts
           article titles and content paragraphs while guarding against SSRF.
        2. **Text & Sensationalism Analysis**:
           Analyzes headlines for curiosity gaps, emotional manipulation, ALL CAPS, and extracts up to 3 verifiable factual claims.
        3. **Multimodal Image Verification**:
           Visually inspects uploaded images against the news context for synthetic generation artifacts, discrepancies, or recycling.
        4. **Real-Time Evidence Retrieval & Claim Verification**:
           Queries DuckDuckGo search for each checkable claim and evaluates whether retrieved evidence *Supports*, *Contradicts*, or leaves claims *Unverified*.
        5. **Transparent Scoring & Explanation**:
           Combines all weighted signals to deliver a discrete verdict (**Real**, **Misleading**, or **Fake**), a credibility score, confidence interval, and citation list.
        """
    )

    st.subheader("⚠️ Known Limitations")
    st.markdown(
        """
        - **Search Snippet Quality**: Verification accuracy depends on the quality and freshness of live search engine snippets.
        - **Image Authenticity**: Visual models highlight potential inconsistencies or context mismatches, but cannot mathematically prove an image is forged.
        - **Breaking News**: Newly unfolding stories may have sparse corroborating sources, resulting in *Unverified* status.
        - **Satire & Sarcasm**: Subtle satirical publications can occasionally be misinterpreted as earnest reporting.
        - **API Quotas**: Free-tier API rate limits may apply under rapid queries.
        """
    )

    st.markdown("---")
    st.subheader("🎓 Project Credits")
    st.markdown(
        """
        - **Course**: Mini Project `BAI507P`
        - **Institution**: Sahyadri College of Engineering and Management
        - **Academic Year**: 2026–2027
        """
    )

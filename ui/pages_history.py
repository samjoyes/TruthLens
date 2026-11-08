"""Streamlit History Page for browsing and managing past analyses."""

import pandas as pd
import streamlit as st

from core.db import delete_analysis, get_analysis, list_history
from core.schemas import AnalysisResult
from ui.components import (
    render_citations_list,
    render_claim_results,
    render_disclaimer,
    render_image_verdict,
    render_scores,
    render_verdict_badge,
)


def render_history_page() -> None:
    """Render the historical analyses browsing and inspection interface."""
    st.header("📜 Past Analyses History")
    st.write("Browse and review previous news authenticity assessments stored in the local SQLite database.")

    records = list_history(limit=50)
    if not records:
        st.info("No past analyses found. Go to 'Analyze' to inspect your first news story!")
        return

    # Convert to DataFrame for tabular display
    df = pd.DataFrame(records)[
        ["id", "created_at", "input_type", "headline", "verdict", "credibility", "confidence"]
    ]
    df.columns = ["ID", "Timestamp", "Type", "Headline", "Verdict", "Credibility (%)", "Confidence (%)"]

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("🔍 Inspect or Delete an Analysis")
    col_select, col_del = st.columns([3, 1])

    available_ids = [r["id"] for r in records]
    with col_select:
        selected_id = st.selectbox(
            "Select Record by ID to view full report:",
            options=available_ids,
            format_func=lambda x: f"ID #{x} — {next(r['headline'] for r in records if r['id'] == x)[:50]}...",
        )

    with col_del:
        st.write("")
        st.write("")
        if st.button("🗑️ Delete Record", type="secondary", use_container_width=True):
            if delete_analysis(selected_id):
                st.success(f"Record #{selected_id} deleted successfully.")
                st.rerun()
            else:
                st.error("Failed to delete record.")

    if selected_id:
        record = get_analysis(selected_id)
        if record and "result" in record:
            result: AnalysisResult = record["result"]
            st.markdown("---")
            st.markdown(f"### Report Details for Record #{selected_id}")
            st.caption(f"**Analyzed on:** {record['created_at']} | **Input:** {record['input_type']} | **Source URL:** {record.get('source_url') or 'N/A'}")
            st.markdown(f"**Headline:** {record['headline']}")

            render_verdict_badge(result.verdict)
            render_scores(
                credibility_score=result.credibility_score,
                confidence=result.confidence,
                clickbait_score=result.text_analysis.clickbait_score,
            )

            st.markdown("#### Summary & Explanation")
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

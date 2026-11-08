"""TruthLens: Online News Credibility and Clickbait Classifier.

Streamlit web application entrypoint.
"""

import os
import streamlit as st

from core.db import init_db
from ui.pages_about import render_about_page
from ui.pages_analyze import render_analyze_page
from ui.pages_history import render_history_page

# Configure Streamlit page settings
st.set_page_config(
    page_title="TruthLens - News Credibility Classifier",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database schema on application boot
init_db()


def main() -> None:
    """Primary application navigation controller."""
    # Sidebar navigation
    with st.sidebar:
        st.title("🔍 TruthLens")
        st.caption("AI-Powered News Authenticity & Clickbait Detection")
        st.markdown("---")

        page_selection = st.radio(
            "Navigate",
            options=["🔎 Analyze News", "📜 History", "ℹ️ About"],
            index=0,
        )

        st.markdown("---")
        # API Key management
        env_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_env_key = bool(env_key and env_key not in ("your_key_here", "your_actual_key"))

        if has_env_key:
            st.success("🔑 Gemini API Key loaded from .env")
        else:
            st.markdown("**🔑 Gemini API Key**")
            input_key = st.text_input(
                "Enter Gemini Key",
                type="password",
                value=st.session_state.get("user_gemini_api_key", ""),
                help="Get a free key at https://aistudio.google.com/ and paste it here or set it in .env.",
                placeholder="AIzaSy...",
                key="sidebar_gemini_key",
            )
            if input_key:
                st.session_state["user_gemini_api_key"] = input_key.strip()
                st.success("API key set for this session!")
            else:
                st.info("💡 Add key in `.env` or paste it above to enable Gemini.")

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size: 0.85rem; color: #888; text-align: center; margin-top: 30px;">
                <strong>TruthLens v1.0</strong><br>
                <em>Verify News. Fight Misinformation.</em>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Route navigation
    if page_selection == "🔎 Analyze News":
        render_analyze_page()
    elif page_selection == "📜 History":
        render_history_page()
    elif page_selection == "ℹ️ About":
        render_about_page()


if __name__ == "__main__":
    main()

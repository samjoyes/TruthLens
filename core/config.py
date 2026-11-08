"""Configuration settings and constants for TruthLens."""

import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
MAX_SEARCH_RESULTS = 5
MAX_CLAIMS = 3
DB_PATH = os.getenv("DB_PATH", "truthlens.db")

TRUSTED_DOMAINS = [
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "thehindu.com",
    "pib.gov.in",
    "who.int",
    "altnews.in",
    "boomlive.in",
    "factcheck.org",
    "snopes.com",
    "politifact.com",
    "afp.com",
]

# Scoring weights (Phase 8)
WEIGHT_CLAIM_VERIFICATION = 0.50
WEIGHT_CONSISTENCY = 0.20
WEIGHT_CLICKBAIT = 0.15
WEIGHT_IMAGE = 0.15


def get_gemini_api_key() -> str:
    """Retrieve Gemini API key from Streamlit secrets, session state, environment, or .env."""
    # 1. Check Streamlit session state and st.secrets if running inside UI
    try:
        import streamlit as st

        if hasattr(st, "session_state") and "user_gemini_api_key" in st.session_state:
            session_key = str(st.session_state.get("user_gemini_api_key") or "").strip()
            if session_key and session_key not in ("your_key_here", "your_actual_key"):
                return session_key

        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            secret_key = str(st.secrets["GEMINI_API_KEY"] or "").strip()
            if secret_key and secret_key not in ("your_key_here", "your_actual_key"):
                return secret_key
    except Exception:
        pass

    # 2. Check environment variable / .env
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    return env_key


GEMINI_API_KEY = get_gemini_api_key()

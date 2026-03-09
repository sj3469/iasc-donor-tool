import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import (
    APP_TITLE,
    APP_SUBTITLE,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    SESSION_BUDGET_USD,
    THREAD_STORE_PATH,
)
from llm import get_response
from queries import get_summary_statistics
from token_tracker import SessionTracker

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="●",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0b1020;
            --panel: #12182b;
            --panel-2: #161d33;
            --border: #27314a;
            --text: #e8ecf7;
            --muted: #9aa4bf;
            --accent: #7c8cff;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: #0f1527;
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: var(--text);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 5rem;
        }

        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--text);
        }

        .app-subtitle {
            color: var(--muted);
            margin-top: -0.25rem;
            margin-bottom: 1rem;
            font-size: 0.98rem;
        }

        .thread-heading {
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 0.2rem;
        }

        .thread-meta {
            color: var(--muted);
            font-size: 0.84rem;
            margin-bottom: 1rem;
        }

        div[data-testid="stTextInput"] input,
        textarea,
        input,
        div[data-baseweb="select"] {
            background-color: var(--panel);
            color: var(--text);
            border: 1px solid var(--border);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Don't forget to call the function so the styles actually apply!
inject_css()

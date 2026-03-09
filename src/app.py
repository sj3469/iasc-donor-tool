import json
import re
import uuid
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# --- THE PATH BRIDGE (CRITICAL FIX) ---
# Forces Streamlit to look inside the 'src' and root folders for your project files
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# --- PROJECT IMPORTS ---
import config
from llm import get_response
from token_tracker import SessionTracker

# Safely extract config variables to prevent ImportErrors
APP_TITLE = getattr(config, "APP_TITLE", "IASC Donor Analytics")
APP_SUBTITLE = getattr(config, "APP_SUBTITLE", "AI-powered donor intelligence for the IASC and The Hedgehog Review")
AVAILABLE_MODELS = getattr(config, "AVAILABLE_MODELS", {"gemini-2.5-flash": "Gemini 2.5 Flash", "gemini-2.0-flash": "Gemini 2.0 Flash"})
DEFAULT_MODEL = getattr(config, "DEFAULT_MODEL", list(AVAILABLE_MODELS.keys())[0])
DB_PATH = root_dir / "data" / "donors.db"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="●",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- DATABASE AUTO-BUILDER ---
# If Streamlit Cloud wipes the temporary database, this builds it back automatically
if not DB_PATH.exists():
    with st.spinner("Building the IASC donor database..."):
        try:
            script_path = root_dir / "data" / "generate_mock_data.py"
            if script_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("generate_mock", script_path)
                mock_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mock_module)
                mock_module.main()
            else:
                st.warning("Database not found, and generate_mock_data.py is missing.")
        except Exception as e:
            st.error(f"Failed to generate database: {e}")

# --- CSS INJECTION (SYNTAX ERROR FIXED) ---
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

inject_css()

# --- INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tracker" not in st.session_state:
    st.session_state.tracker = SessionTracker()

# --- SIDEBAR: FILTERS & FAQ ---
with st.sidebar:
    st.title("⚙️ Settings")
    selected_model = st.selectbox("Model", list(AVAILABLE_MODELS.keys()), index=0)
    
    st.divider()
    st.markdown("### 🔍 Quick Filters")
    donor_status = st.selectbox("Donor Status", ["All", "Active", "Lapsed", "Prospect"])
    state_filter = st.selectbox("State", ["All", "VA", "NY", "CA", "TX", "DC", "MD"])
    
    st.divider()
    st.markdown("### ❓ FAQ")
    with st.expander("Who are my Top Donors?"):
        st.write("Ask: 'Who are the top 10 donors by lifetime giving?'")
    with st.expander("How do I find lapsed donors?"):
        st.write("Ask: 'Show me donors who haven't given since 2023.'")

    st.divider()
    try:
        st.markdown(st.session_state.tracker.format_sidebar())
    except Exception:
        pass # Failsafe if token tracker is still initializing
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN UI ---
st.title(APP_TITLE)
st.markdown(f'<p class="app-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT & FILE UPLOADER ---
with st.container():
    uploaded_file = st.file_uploader("Upload a donor report (CSV/PDF) for AI analysis", type=['csv', 'pdf', 'txt'])
    
    if prompt := st.chat_input("Ask about your donor community..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            with st.status("Consulting IASC records...", expanded=True) as status:
                response, usage = get_response(
                    user_message=prompt,
                    conversation_history=st.session_state.messages[:-1],
                    model=selected_model,
                    session_tracker=st.session_state.tracker,
                    attachment=uploaded_file
                )
                status.update(label="Complete!", state="complete", expanded=False)
            
            response_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

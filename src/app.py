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
            --accent-soft: rgba(124, 140, 255, 0.18);
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

        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--text);
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 6rem;
        }

        .app-header {
            margin-bottom: 0.25rem;
        }

        .app-subtitle {
            color: var(--muted);
            margin-top: -0.25rem;
            margin-bottom: 1rem;
            font-size: 0.98rem;
        }

        .thread-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 0.25rem 0 1rem 0;
            color: var(--text);
        }

        .thread-meta {
            color: var(--muted);
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] > div,
        div[data-testid="stMultiSelect"] > div,
        textarea,
        input {
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextInput"] input:focus,
        textarea:focus,
        input:focus {
            border: 1px solid #3d4f78 !important;
            box-shadow: 0 0 0 1px #3d4f78 !important;
            outline: none !important;
        }

        div[data-testid="stButton"] button {
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
        }

        div[data-testid="stButton"] button:hover {
            border-color: #3d4f78 !important;
            background: var(--panel-2) !important;
        }

        div[data-testid="stChatMessage"] {
            background: transparent !important;
        }

        div[data-testid="stChatInput"] {
            background: rgba(11, 16, 32, 0.86) !important;
        }

        div[data-testid="stChatInput"] > div {
            background: var(--panel) !important;
            border: 1px solid var(--border) !important;
            border-radius: 18px !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] textarea {
            color: var(--text) !important;
        }

        .model-chip {
            position: fixed;
            right: 1.35rem;
            bottom: 5.55rem;
            z-index: 999;
            background: rgba(18, 24, 43, 0.92);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.4rem 0.8rem;
            font-size: 0.82rem;
            backdrop-filter: blur(8px);
        }

        .history-caption {
            color: var(--muted);
            font-size: 0.8rem;
            margin-top: -0.25rem;
            margin-bottom: 0.5rem;
        }

        .usage-box {
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            background: var(--panel);
        }

        .muted {
            color: var(--muted);
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            background: var(--panel) !important;
        }

        .stCaption {
            color: var(--muted) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def make_thread(title: str = "New thread") -> dict:
    ts = now_iso()
    return {
        "id": uuid.uuid4().hex,
        "title": title,
        "created_at": ts,
        "updated_at": ts,
        "messages": [],
    }


def load_threads() -> list[dict]:
    path = Path(THREAD_STORE_PATH)
    if not path.exists():
        return [make_thread()]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return [make_thread()]


def save_threads(threads: list[dict]) -> None:
    Path(THREAD_STORE_PATH).write_text(
        json.dumps(threads, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ensure_state() -> None:
    if "threads" not in st.session_state:
        st.session_state.threads = load_threads()
    if "active_thread_id" not in st.session_state:
        st.session_state.active_thread_id = st.session_state.threads[0]["id"]
    if "tracker" not in st.session_state:
        st.session_state.tracker = SessionTracker()
    if "thread_search" not in st.session_state:
        st.session_state.thread_search = ""


def get_active_thread() -> dict:
    for thread in st.session_state.threads:
        if thread["id"] == st.session_state.active_thread_id:
            return thread
    fallback = make_thread()
    st.session_state.threads.insert(0, fallback)
    st.session_state.active_thread_id = fallback["id"]
    save_threads(st.session_state.threads)
    return fallback


def thread_matches_search(thread: dict, query: str) -> bool:
    if not query:
        return True
    q = query.lower().strip()
    if q in thread.get("title", "").lower():
        return True
    for message in thread.get("messages", []):
        if q in message.get("content", "").lower():
            return True
    return False


def format_thread_title(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", prompt).strip()
    if not cleaned:
        return "New thread"
    words = cleaned.split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "…"
    return title


def add_message(role: str, content: str, attachments: list[str] | None = None) -> None:
    thread = get_active_thread()
    thread["messages"].append(
        {
            "role": role,
            "content": content,
            "attachments": attachments or [],
            "timestamp": now_iso(),
        }
    )
    thread["updated_at"] = now_iso()
    if role == "user" and len([m for m in thread["messages"] if m["role"] == "user"]) == 1:
        thread["title"] = format_thread_title(content)
    save_threads(st.session_state.threads)


def create_new_thread() -> None:
    thread = make_thread()
    st.session_state.threads.insert(0, thread)
    st.session_state.active_thread_id = thread["id"]
    save_threads(st.session_state.threads)


def parse_chat_submission(value) -> tuple[str, list]:
    if value is None:
        return "", []

    if isinstance(value, str):
        return value.strip(), []

    text = ""
    files = []

    if hasattr(value, "text"):
        text = value.text or ""
    elif isinstance(value, dict):
        text = value.get("text", "")
    else:
        try:
            text = value["text"]
        except Exception:
            text = ""

    if hasattr(value, "files"):
        files = list(value.files or [])
    elif isinstance(value, dict):
        files = list(value.get("files", []) or [])
    else:
        try:
            files = list(value["files"])
        except Exception:
            files = []

    return text.strip(), files


def get_state_options() -> list[str]:
    fallback = ["All", "VA", "NY", "DC", "MD", "MA", "IL", "CA", "TX", "FL", "PA", "OH", "GA", "NC", "WA", "CO", "MN", "MO", "AZ", "TN", "NJ"]
    try:
        result = get_summary_statistics(group_by="state")
        rows = result.get("results", [])
        states = sorted([r.get("group_value") for r in rows if r.get("group_value")])
        return ["All"] + states if states else fallback
    except Exception:
        return fallback


def build_effective_prompt(prompt: str, donor_status_filter: str, state_filter: str) -> str:
    notes = []
    if donor_status_filter != "All":
        notes.append(f"donor_status = {donor_status_filter}")
    if state_filter != "All":
        notes.append(f"state = {state_filter}")

    if not notes:
        return prompt

    return (
        prompt
        + "\n\nDefault sidebar filters to apply if relevant:\n- "
        + "\n- ".join(notes)
        + "\nIf the user's request explicitly conflicts with these defaults, follow the user's request."
    )


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.text(message["content"])
        else:
            st.markdown(message["content"])
            attachments = message.get("attachments", []) or []
            if attachments:
                st.caption("Attached: " + ", ".join(attachments))


ensure_state()
inject_css()

with st.sidebar:
    st.text_input(
        "Search",
        key="thread_search",
        placeholder="Search threads",
        label_visibility="collapsed",
    )

    if st.button("+ New thread", use_container_width=True):
        create_new_thread()
        st.rerun()

    st.markdown("#### History")
    filtered

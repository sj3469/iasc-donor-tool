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
            --bg: #f7f8fb;
            --panel: #ffffff;
            --panel-soft: #f8f9fc;
            --border: #d8deea;
            --text: #172033;
            --muted: #65708a;
            --accent: #24324a;
            --accent-hover: #1c273b;
            --chip: #eef2f8;
            --navy: #0f1728;
            --sidebar-bg: #0f1728;
            --sidebar-border: #25324a;
            --sidebar-text: #ffffff;
            --sidebar-line: #eef2f8;
            --soft-line: #e9edf5;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        body {
            color: var(--text);
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        /* ---------- top chrome ---------- */

        .stApp > header,
        header,
        header[data-testid="stHeader"],
        [data-testid="stHeader"] {
            background: #ffffff !important;
            border-bottom: 1px solid var(--soft-line) !important;
        }

        [data-testid="stDecoration"] {
            background: #ffffff !important;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"] {
            background: #ffffff !important;
            color: var(--navy) !important;
        }

        [data-testid="stHeader"] *,
        [data-testid="stToolbar"] *,
        [data-testid="stStatusWidget"] * {
            color: var(--navy) !important;
        }

        [data-testid="stHeader"] button,
        [data-testid="stToolbar"] button,
        [data-testid="stStatusWidget"] button,
        button[kind="header"],
        button[kind="headerNoPadding"] {
            color: var(--navy) !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        [data-testid="stHeader"] a,
        [data-testid="stToolbar"] a,
        [data-testid="stStatusWidget"] a,
        [data-testid="stHeader"] span,
        [data-testid="stToolbar"] span,
        [data-testid="stStatusWidget"] span,
        [data-testid="stHeader"] div,
        [data-testid="stToolbar"] div,
        [data-testid="stStatusWidget"] div {
            color: var(--navy) !important;
        }

        [data-testid="stHeader"] svg,
        [data-testid="stToolbar"] svg,
        [data-testid="stStatusWidget"] svg,
        button[kind="header"] svg,
        button[kind="headerNoPadding"] svg {
            fill: var(--navy) !important;
            stroke: var(--navy) !important;
            color: var(--navy) !important;
        }

        [data-testid="stHeader"] svg *,
        [data-testid="stToolbar"] svg *,
        [data-testid="stStatusWidget"] svg *,
        button[kind="header"] svg *,
        button[kind="headerNoPadding"] svg * {
            fill: var(--navy) !important;
            stroke: var(--navy) !important;
        }

        [data-testid="stStatusWidget"] img,
        [data-testid="stToolbar"] img,
        [data-testid="stHeader"] img {
            filter: brightness(0) saturate(100%) invert(8%) sepia(18%) saturate(1111%) hue-rotate(184deg) brightness(94%) contrast(95%) !important;
        }

        [data-testid="collapsedControl"] button,
        [data-testid="collapsedControl"] svg,
        [data-testid="collapsedControl"] svg * {
            color: var(--navy) !important;
            fill: var(--navy) !important;
            stroke: var(--navy) !important;
        }

        /* ---------- sidebar ---------- */

        [data-testid="stSidebar"] {
            background: var(--sidebar-bg) !important;
            border-right: 1px solid var(--sidebar-border);
        }

        [data-testid="stSidebar"] * {
            color: var(--sidebar-text) !important;
        }

        [data-testid="stSidebar"] hr {
            border: none !important;
            border-top: 1px solid var(--sidebar-line) !important;
        }

        [data-testid="stSidebar"] div[data-testid="stTextInput"] input {
            background: #162033 !important;
            color: #ffffff !important;
            border: 1px solid #31415f !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] div[data-testid="stTextInput"] input::placeholder {
            color: #ffffff !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] div[data-testid="stTextInput"] input:focus {
            border: 1px solid #5e7398 !important;
            box-shadow: 0 0 0 1px #5e7398 !important;
            outline: none !important;
        }

        [data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: #162033 !important;
            color: #ffffff !important;
            border: 1px solid #31415f !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] {
            border: 1px solid #31415f !important;
            background: #162033 !important;
            border-radius: 14px !important;
        }

        .usage-box {
            border: 1px solid #31415f;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            background: #162033;
        }

        .usage-box div {
            color: #ffffff !important;
        }

        /* ---------- main content ---------- */

        .block-container {
            max-width: 980px;
            padding-top: 1.25rem;
            padding-bottom: 5rem;
        }

        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--text);
        }

        .app-subtitle {
            color: var(--muted);
            margin-top: -0.15rem;
            margin-bottom: 1rem;
            font-size: 0.98rem;
        }

        .thread-heading {
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 0.2rem;
            color: var(--text);
        }

        .thread-meta {
            color: var(--muted);
            font-size: 0.84rem;
            margin-bottom: 1rem;
        }

        .model-chip {
            display: inline-block;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.32rem 0.72rem;
            font-size: 0.82rem;
            color: var(--text);
            background: var(--chip);
            margin-bottom: 0.8rem;
        }

        /* ---------- buttons ---------- */

        div[data-testid="stButton"] button {
            background: var(--accent) !important;
            color: #ffffff !important;
            border: 1px solid var(--accent) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }

        div[data-testid="stButton"] button:hover {
            background: var(--accent-hover) !important;
            border-color: var(--accent-hover) !important;
        }

        /* ---------- chat input ---------- */

        div[data-testid="stChatInput"] {
            background: transparent !important;
        }

        div[data-testid="stChatInput"] form {
            background: #ffffff !important;
            border: 1px solid transparent !important;
            border-radius: 22px !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] form:focus-within {
            border: 1px solid transparent !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] > div,
        div[data-testid="stChatInput"] section,
        div[data-testid="stChatInput"] label {
            background: #ffffff !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] textarea {
            background: #ffffff !important;
            color: var(--text) !important;
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }

        div[data-testid="stChatInput"] textarea::placeholder {
            color: #6c7892 !important;
            opacity: 1 !important;
        }

        div[data-testid="stChatInput"] textarea:focus {
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
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
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL


def get_active_thread() -> dict:
    for thread in st.session_state.threads:
        if thread["id"] == st.session_state.active_thread_id:
            return thread

    thread = make_thread()
    st.session_state.threads.insert(0, thread)
    st.session_state.active_thread_id = thread["id"]
    save_threads(st.session_state.threads)
    return thread


def format_thread_title(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", prompt).strip()
    if not cleaned:
        return "New thread"
    words = cleaned.split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "…"
    return title


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


def create_new_thread() -> None:
    thread = make_thread()
    st.session_state.threads.insert(0, thread)
    st.session_state.active_thread_id = thread["id"]
    save_threads(st.session_state.threads)


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

    if role == "user":
        user_count = len([m for m in thread["messages"] if m["role"] == "user"])
        if user_count == 1:
            thread["title"] = format_thread_title(content)

    save_threads(st.session_state.threads)


def get_state_options() -> list[str]:
    fallback = [
        "All", "VA", "NY", "DC", "MD", "MA", "IL", "CA", "TX", "FL",
        "PA", "OH", "GA", "NC", "WA", "CO", "MN", "MO", "AZ", "TN", "NJ"
    ]
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
        "Apply these sidebar filters unless the user explicitly overrides them:\n- "
        + "\n- ".join(notes)
        + "\n\nUser question:\n"
        + prompt
    )


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.text(message["content"])
        else:
            st.markdown(message["content"])
            attachments = message.get("attachments") or []
            if attachments:
                st.caption("Attached: " + ", ".join(attachments))


def session_spend_and_remaining() -> tuple[float, float]:
    spent = getattr(st.session_state.tracker, "total_cost", 0.0) or 0.0
    remaining = max(0.0, SESSION_BUDGET_USD - spent)
    return spent, remaining


def render_usage_box(container) -> None:
    spent, remaining = session_spend_and_remaining()
    container.markdown("#### Session usage")
    container.markdown(
        f"""
        <div class="usage-box">
            <div>Questions: {len(st.session_state.tracker.responses)}</div>
            <div>API calls: {st.session_state.tracker.total_api_calls}</div>
            <div>Input tokens: {st.session_state.tracker.total_input_tokens:,}</div>
            <div>Output tokens: {st.session_state.tracker.total_output_tokens:,}</div>
            <div>Spent: ${spent:.4f}</div>
            <div>Left: ${remaining:.4f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def parse_chat_submission(submission) -> tuple[str, list]:
    if submission is None:
        return "", []

    if isinstance(submission, str):
        return submission.strip(), []

    text = ""
    files = []

    try:
        text = submission.text or ""
    except Exception:
        try:
            text = submission.get("text", "")
        except Exception:
            text = ""

    try:
        files = list(submission.files or [])
    except Exception:
        try:
            files = list(submission.get("files", []) or [])
        except Exception:
            files = []

    return text.strip(), files


ensure_state()
inject_css()
state_options = get_state_options()
usage_placeholder = None

with st.sidebar:
    selected_model = st.selectbox(
        "Model",
        list(AVAILABLE_MODELS.keys()),
        format_func=lambda x: AVAILABLE_MODELS[x],
        index=list(AVAILABLE_MODELS.keys()).index(
            st.session_state.get("selected_model", DEFAULT_MODEL)
        ),
    )
    st.session_state.selected_model = selected_model

    st.text_input(
        "Search threads",
        key="thread_search",
        placeholder="Search threads",
        label_visibility="collapsed",
    )

    if st.button("+ New thread", use_container_width=True):
        create_new_thread()
        st.rerun()

    st.markdown("#### History")
    sorted_threads = sorted(
        st.session_state.threads,
        key=lambda t: t.get("updated_at", ""),
        reverse=True,
    )

    history_threads = [t for t in sorted_threads if t.get("messages")]
    visible_threads = [
        t for t in history_threads
        if thread_matches_search(t, st.session_state.thread_search)
    ]

    if not visible_threads:
        st.caption("No matching threads")
    else:
        for thread_item in visible_threads:
            label = thread_item["title"] or "Untitled thread"
            prefix = "• " if thread_item["id"] == st.session_state.active_thread_id else ""
            if st.button(f"{prefix}{label}", key=f"thread_{thread_item['id']}", use_container_width=True):
                st.session_state.active_thread_id = thread_item["id"]
                st.rerun()

    st.divider()

    st.markdown("#### Quick filters")
    donor_status_filter = st.selectbox(
        "Donor status",
        ["All", "active", "lapsed", "prospect", "new_donor"],
        index=0,
    )
    state_filter = st.selectbox(
        "State",
        state_options,
        index=0,
    )

    st.divider()

    st.markdown("#### FAQ")
    with st.expander("What can I ask here?"):
        st.markdown(
            "- Show top donors overall\n"
            "- Show top donors in VA\n"
            "- Show top donors in New York\n"
            "- Show top donors in ZIP 10027\n"
            "- Find lapsed donors worth re-engaging\n"
            "- Identify high-potential prospects\n"
            "- Summarize geographic donor distribution\n"
            "- Show summary by state\n"
            "- Plan a fundraising trip in DC\n"
            "- Show donor 003XXXXXXXXXXXXXXX"
        )

    with st.expander("How do filters work?"):
        st.markdown(
            "Filters act as default constraints for broad queries. "
            "If you ask for a different state or segment explicitly, your prompt overrides the defaults."
        )

    st.divider()
    usage_placeholder = st.empty()
    render_usage_box(usage_placeholder)

thread = get_active_thread()

st.title(APP_TITLE)
st.markdown(f'<div class="app-subtitle">{APP_SUBTITLE}</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="model-chip">Model: {AVAILABLE_MODELS.get(selected_model, selected_model)}</div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="thread-heading">{thread["title"]}</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="thread-meta">Thread updated: {thread.get("updated_at", "")}</div>',
    unsafe_allow_html=True,
)

for message in thread["messages"]:
    render_message(message)

submission = st.chat_input(
    "Ask about the donors",
    accept_file="multiple",
    file_type=["png", "jpg", "jpeg", "pdf", "txt", "csv"],
    key="main_chat_input",
)

prompt, uploaded_files = parse_chat_submission(submission)

if prompt or uploaded_files:
    attachment_names = [f.name for f in uploaded_files]
    effective_prompt = build_effective_prompt(prompt, donor_status_filter, state_filter) if prompt else ""

    user_display = prompt if prompt else "[Files uploaded]"
    add_message("user", user_display, attachments=attachment_names)

    with st.chat_message("user"):
        if prompt:
            st.markdown(prompt)
        else:
            st.markdown("[Files uploaded]")
        if attachment_names:
            st.caption("Attached: " + ", ".join(attachment_names))

    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        try:
            with st.status("Analyzing donor database...", expanded=True) as status:
                response, usage = get_response(
                    user_message=effective_prompt if prompt else "Please analyze the attached files if relevant.",
                    conversation_history=thread["messages"][:-1],
                    model=selected_model,
                    session_tracker=st.session_state.tracker,
                    attachment=uploaded_files,
                )
                status.update(label="Analysis complete", state="complete", expanded=False)

            response_placeholder.text(response)
            add_message("assistant", response)

            st.caption(
                f"Prompt tokens: {getattr(usage, 'prompt_token_count', 0)} | "
                f"Output tokens: {getattr(usage, 'candidates_token_count', 0)}"
            )

            if usage_placeholder is not None:
                render_usage_box(usage_placeholder)

        except Exception as e:
            st.error(f"Request failed: {e}")

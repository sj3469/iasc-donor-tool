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
            --bg-soft: #f1f3f8;
            --panel: #ffffff;
            --panel-2: #f8f9fc;
            --border: #d8deea;
            --text: #172033;
            --muted: #65708a;
            --accent: #27314a;
            --accent-soft: #e9edf7;
            --chip: #eef2f8;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: var(--panel);
            border-right: 1px solid var(--border);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 5rem;
            max-width: 980px;
        }

        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--text);
        }

        .app-subtitle {
            color: var(--muted);
            margin-top: -0.2rem;
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
        div[data-baseweb="select"] > div,
        div[data-testid="stFileUploader"] section {
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextInput"] input:focus,
        textarea:focus,
        input:focus {
            border: 1px solid #9aa8c6 !important;
            box-shadow: 0 0 0 1px #9aa8c6 !important;
            outline: none !important;
        }

        div[data-testid="stButton"] button {
            background: var(--accent) !important;
            color: white !important;
            border: 1px solid var(--accent) !important;
            border-radius: 12px !important;
        }

        div[data-testid="stButton"] button:hover {
            background: #1c2538 !important;
            border-color: #1c2538 !important;
        }

        div[data-testid="stChatInput"] {
            background: transparent !important;
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

        .usage-box {
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            background: var(--panel);
        }

        .model-chip {
            display: inline-block;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.32rem 0.7rem;
            font-size: 0.82rem;
            color: var(--text);
            background: var(--chip);
            margin-bottom: 0.75rem;
        }

        .attach-box {
            border: 1px dashed var(--border);
            border-radius: 14px;
            padding: 0.5rem 0.8rem 0.25rem 0.8rem;
            background: var(--panel-2);
            margin-bottom: 0.75rem;
        }

        .small-muted {
            color: var(--muted);
            font-size: 0.84rem;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            background: var(--panel) !important;
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
            attachments = message.get("attachments") or []
            if attachments:
                st.caption("Attached: " + ", ".join(attachments))


def session_spend_and_remaining() -> tuple[float, float]:
    spent = getattr(st.session_state.tracker, "total_cost", 0.0) or 0.0
    remaining = max(0.0, SESSION_BUDGET_USD - spent)
    return spent, remaining


ensure_state()
inject_css()
state_options = get_state_options()

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
    sorted_threads = sorted(
        st.session_state.threads,
        key=lambda t: t.get("updated_at", ""),
        reverse=True,
    )
    visible_threads = [
        t for t in sorted_threads
        if thread_matches_search(t, st.session_state.thread_search)
    ]

    if not visible_threads:
        st.caption("No matching threads")
    else:
        for thread_item in visible_threads:
            label = thread_item["title"] or "Untitled thread"
            if thread_item["id"] == st.session_state.active_thread_id:
                label = "• " + label
            if st.button(label, key=f"thread_{thread_item['id']}", use_container_width=True):
                st.session_state.active_thread_id = thread_item["id"]
                st.rerun()

    st.divider()

    selected_model = st.selectbox(
        "Model",
        list(AVAILABLE_MODELS.keys()),
        format_func=lambda x: AVAILABLE_MODELS[x],
        index=list(AVAILABLE_MODELS.keys()).index(
            st.session_state.get("selected_model", DEFAULT_MODEL)
        ),
    )
    st.session_state["selected_model"] = selected_model

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

    with st.expander("Why are some answers short?"):
        st.markdown(
            "Many common donor questions are answered directly from local database helpers, "
            "so responses may be concise by design."
        )

    st.divider()

    spent, remaining = session_spend_and_remaining()
    st.markdown("#### Session usage")
    st.markdown(
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

st.markdown('<div class="attach-box">', unsafe_allow_html=True)
st.markdown('<div class="small-muted">+ Attach files or images</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "Attach files",
    accept_multiple_files=True,
    type=["png", "jpg", "jpeg", "pdf", "txt", "csv"],
    label_visibility="collapsed",
    key="attachment_uploader",
)
st.markdown("</div>", unsafe_allow_html=True)

prompt = st.chat_input("Ask about your donor community...")

if prompt:
    attachment_names = [f.name for f in (uploaded_files or [])]
    effective_prompt = build_effective_prompt(prompt, donor_status_filter, state_filter)

    add_message("user", prompt, attachments=attachment_names)

    with st.chat_message("user"):
        st.markdown(prompt)
        if attachment_names:
            st.caption("Attached: " + ", ".join(attachment_names))

    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        try:
            with st.status("Analyzing donor database...", expanded=True) as status:
                response, usage = get_response(
                    user_message=effective_prompt,
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

        except Exception as e:
            st.error(f"Request failed: {e}")

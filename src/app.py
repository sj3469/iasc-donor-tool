import streamlit as st
import config
from llm import get_response, scrub_tool_calls, convert_to_csv
from token_tracker import SessionTracker
import inspect

# --- PAGE CONFIG ---
st.set_page_config(page_title=config.APP_TITLE, page_icon="📊", layout="wide")

def inject_css():
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { background-color: #0b1020 !important; }
        .suggestion-chip {
            display: inline-block;
            padding: 5px 15px;
            margin: 5px;
            border: 1px solid #0b57d0;
            border-radius: 15px;
            color: #0b57d0;
            cursor: pointer;
            font-size: 0.85rem;
        }
        </style>
    """, unsafe_allow_html=True)
inject_css()

# --- INITIALIZATION ---
if "messages" not in st.session_state: st.session_state.messages = []
if "tracker" not in st.session_state: st.session_state.tracker = SessionTracker()
if "pending_prompt" not in st.session_state: st.session_state.pending_prompt = None

# --- SIDEBAR (REDUCED PER PROFESSOR FEEDBACK) ---
with st.sidebar:
    st.title("Settings")
    selected_model = st.selectbox("Model", list(config.AVAILABLE_MODELS.keys()), index=0)
    st.divider()
    st.markdown(st.session_state.tracker.format_sidebar())
    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN UI ---
st.title(config.APP_TITLE)
st.caption(config.APP_SUBTITLE)

# --- CHAT RENDER ---
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CONTEXTUAL SUGGESTIONS (UX IMPROVEMENT) ---
if not st.session_state.messages:
    st.info("👋 Welcome. Try asking a question about your donor base below.")
else:
    # Logic to provide smart chips based on last interaction
    st.write("Suggested:")
    cols = st.columns(3)
    with cols[0]:
        if st.button("📈 Show Trends"): st.session_state.pending_prompt = "Give me a summary of giving trends."
    with cols[1]:
        if st.button("📍 Map Donors"): st.session_state.pending_prompt = "What is the geographic distribution?"
    with cols[2]:
        if st.button("⏳ Lapsed List"): st.session_state.pending_prompt = "Show me lapsed donors since 2023."

# --- INPUT HANDLING ---
prompt = st.chat_input("Ask about your donor community...")
if prompt or st.session_state.pending_prompt:
    active_prompt = prompt or st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"): st.markdown(active_prompt)

    with st.status("Analyzing records...") as status:
        response_text, usage = get_response(
            user_message=active_prompt,
            conversation_history=st.session_state.messages[:-1],
            model=selected_model,
            session_tracker=st.session_state.tracker
        )
        status.update(label="Analysis complete", state="complete", expanded=False)

    st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.rerun()

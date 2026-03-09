import streamlit as st
import os
import sys
from pathlib import Path

# --- THE PATH BRIDGE ---
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from config import APP_TITLE, APP_SUBTITLE, AVAILABLE_MODELS, DEFAULT_MODEL
from llm import get_response
from token_tracker import SessionTokenTracker

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "tracker" not in st.session_state:
    st.session_state.tracker = SessionTokenTracker()

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
    st.markdown(st.session_state.tracker.format_sidebar())
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN UI ---
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT & FILE UPLOADER ---
# This adds the file upload feature directly in the chat workflow
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

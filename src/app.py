import streamlit as st
import os
import sys
from pathlib import Path

# Add the current directory to the system path to fix ImportErrors
sys.path.append(str(Path(__file__).parent))

# Now import project files
from config import APP_TITLE, APP_SUBTITLE, AVAILABLE_MODELS, DEFAULT_MODEL
from llm import get_response
from token_tracker import SessionTokenTracker

# 1. Page Configuration
st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

# 2. Initialize Session States
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tracker" not in st.session_state:
    st.session_state.tracker = SessionTokenTracker()

# 3. Sidebar UI
with st.sidebar:
    st.title("⚙️ Settings")
    selected_model = st.selectbox(
        "Select Model", 
        list(AVAILABLE_MODELS.keys()), 
        format_func=lambda x: AVAILABLE_MODELS[x], 
        index=list(AVAILABLE_MODELS.keys()).index(DEFAULT_MODEL)
    )
    
    st.divider()
    st.markdown("### 📁 Data Source")
    st.info("Connected: `mock_dataset3.csv`")
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# 4. Main UI Header [Restores your missing titles]
st.title(APP_TITLE)
st.subheader(APP_SUBTITLE)

# 5. Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about your donor community..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        with st.status("Analyzing IASC database...", expanded=True) as status:
            response, usage = get_response(
                user_message=prompt,
                conversation_history=st.session_state.messages[:-1],
                model=selected_model,
                session_tracker=st.session_state.tracker
            )
            status.update(label="Analysis Complete!", state="complete", expanded=False)
        
        response_placeholder.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

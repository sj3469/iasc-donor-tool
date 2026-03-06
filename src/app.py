"""
IASC Donor Analytics — Expert Gemini-Style UI with Sidebar
Main entry point: streamlit run src/app.py
"""

import sys
import pandas as pd
import sqlite3
from pathlib import Path
import streamlit as st
import uuid

# 1. Path & Import Setup
sys.path.insert(0, str(Path(__file__).parent))
from config import APP_TITLE, APP_SUBTITLE, AVAILABLE_MODELS, DEFAULT_MODEL, DB_PATH
from llm import get_response
from token_tracker import SessionTracker
from knowledge import get_knowledge_token_estimate

# 2. Page & Theme Configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Gemini-style look and fixed-width sidebar
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        min-width: 320px;
        max-width: 320px;
    }
    .stChatMessage { border-radius: 12px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. Data Initialization (Fix: Database Not Found)
def initialize_database():
    """Converts the uploaded CSV to the SQLite DB format the app expects."""
    if not DB_PATH.exists():
        csv_path = Path("data/mock_dataset3.csv")
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            conn = sqlite3.connect(DB_PATH)
            # Table 'contacts' is required for the sidebar KPI logic
            df.to_sql("contacts", conn, index=False, if_exists="replace")
            conn.close()

initialize_database()

# 4. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tracker" not in st.session_state:
    st.session_state.tracker = SessionTracker()
if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# 5. SIDEBAR (The restored navigation and stats panel)
with st.sidebar:
    st.title(f"📊 {APP_TITLE}")
    st.caption("IASC Donor Intelligence")
    st.divider()

    # File Uploader (Gemini-style attachment)
    st.subheader("📎 Attach Files")
    uploaded_file = st.file_uploader(
        "Add lists or reports", 
        type=["pdf", "csv", "png", "jpg"],
        label_visibility="collapsed"
    )
    if uploaded_file:
        st.info(f"Attached: {uploaded_file.name}")

    st.divider()

    # Real-time KPIs from mock_dataset3.csv
    st.subheader("IASC Quick Stats")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        stats = cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN donor_status = 'active' THEN 1 END) as active,
                ROUND(SUM(COALESCE(total_gifts, 0)), 0) as total_giving
            FROM contacts
        """).fetchone()
        conn.close()

        c1, c2 = st.columns(2)
        c1.metric("Contacts", f"{stats['total']:,}")
        c2.metric("Active", stats['active'])
        st.metric("Total Giving", f"${stats['total_giving']:,.0f}")
    except:
        st.caption("Stats will sync on data load...")

    st.divider()
    
    # Model & Clearing Tools
    with st.expander("⚙️ Settings"):
        model_labels = list(AVAILABLE_MODELS.values())
        sel = st.selectbox("Model", options=model_labels)
        for mid, lab in AVAILABLE_MODELS.items():
            if lab == sel: st.session_state.selected_model = mid
        st.caption(f"Knowledge Base: ~{get_knowledge_token_estimate():,} tokens")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.tracker = SessionTracker()
        st.rerun()

# 6. MAIN CHAT AREA
st.markdown("<h2 style='text-align: center;'>Ask anything about your donor community</h2>", unsafe_allow_html=True)

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("usage"):
            st.caption(msg["usage"].format_inline(st.session_state.selected_model))

# Sticky Input and Response Logic
if prompt := st.chat_input("Ask a question..."):
    # User message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Assistant response
    with st.chat_message("assistant"):
        with st.status("Analyzing...", expanded=True) as status:
            try:
                response_text, response_usage = get_response(
                    user_message=prompt,
                    conversation_history=st.session_state.messages[:-1],
                    model=st.session_state.selected_model,
                    session_tracker=st.session_state.tracker,
                    progress_callback=lambda m: status.update(label=m),
                    st_session_id=st.session_state.session_id,
                    attachment=uploaded_file
                )
                status.update(label="Complete", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Error", state="error", expanded=False)
                response_text = f"**Error:** {e}"
                response_usage = None

        st.markdown(response_text)
        
        # Export button for tabular data
        if any(kw in response_text.lower() for kw in ["list", "top", "donors"]):
             st.download_button("📥 Export CSV", response_text, "export.csv", "text/csv")

        st.session_state.messages.append({
            "role": "assistant", 
            "content": response_text, 
            "usage": response_usage
        })

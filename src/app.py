import streamlit as st
# ... (keep your existing imports)

# ─── Gemini-Style Custom CSS ──────────────────────────────────────────────────
st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
    }
    /* Style the sidebar like Gemini's left nav */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)

# ─── Main Header ──────────────────────────────────────────────────────────────
# Use a cleaner, centered header
st.markdown("<h1 style='text-align: center;'>IASC Donor Intelligence</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Ask anything about your donor community.</p>", unsafe_allow_html=True)

# ─── Chat Logic ───────────────────────────────────────────────────────────────
# (Existing chat history logic goes here)

# Use the sticky chat input that mirrors the Gemini experience
if prompt := st.chat_input("Ask a question..."):
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    
    # ... (rest of your response logic)

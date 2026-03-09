import os
import sys
import re
import inspect
from pathlib import Path
import streamlit as st

# --- THE PATH BRIDGE ---
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

APP_TITLE = getattr(config, "APP_TITLE", "IASC Donor Analytics")
APP_SUBTITLE = getattr(config, "APP_SUBTITLE", "AI-powered donor intelligence")
AVAILABLE_MODELS = getattr(config, "AVAILABLE_MODELS", {"gemini-2.0-flash": "Gemini 2.0 Flash"})
DEFAULT_MODEL = getattr(config, "DEFAULT_MODEL", list(AVAILABLE_MODELS.keys())[0])
DB_PATH = root_dir / "data" / "donors.db"

# --- PAGE CONFIG ---
st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# --- DATABASE AUTO-BUILDER ---
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
        except Exception as e:
            st.error(f"Failed to generate database: {e}")

# --- HELPERS ---
def convert_to_csv(text):
    lines = text.strip().split('\n')
    csv_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            line = line[1:-1]
            if set(line.replace('|', '').replace('-', '').replace(' ', '')) == set():
                continue
            row = [col.strip().replace('"', '""') for col in line.split('|')]
            csv_row = ','.join(f'"{col}"' if ',' in col else col for col in row)
            csv_lines.append(csv_row)
    if csv_lines:
        return "\n".join(csv_lines).encode('utf-8')
    return text.encode('utf-8')

def scrub_tool_calls(text):
    """Aggressively removes technical logs, Tool Calls, and mentions of 'fields'."""
    cleaned = re.sub(r'Tool Call:[\s\S]*?Results:[\s\S]*?\]\n*```?\n*', '', text)
    cleaned = re.sub(r'\*?\*?Tool Call:?\*?\*?[\s\S]*?Results:[\s\S]*?(?=\n\n(?:#|\*|[A-Z])|\Z)', '', cleaned)
    cleaned = re.sub(r'^Here are the top 10 donors by total giving:\n*(?=Top 10 Donors)', '', cleaned, flags=re.IGNORECASE)
    
    # Eradicate mentions of database fields/schema
    cleaned = re.sub(r'(?i)^(?:Fields|Columns):\s*.*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'(?i)based on the fields.*?(?=\n|$)', '', cleaned)
    cleaned = re.sub(r'(?i)\(Query:.*\)', '', cleaned) 
    return cleaned.strip()

# --- BULLETPROOF CSS INJECTION ---
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { 
            --main-bg: #ffffff; 
            --main-text: #111827; 
            --border-light: #e5e7eb;
            --focus-grey: #9ca3af;
            --accent-blue: #0b57d0;
            
            --sidebar-bg: #0b1020; 
            --sidebar-border: #27314a;
            --sidebar-text: #ffffff;
        }
        
        /* 1. Main App Styling */
        [data-testid="stAppViewContainer"] { background-color: var(--main-bg) !important; }
        [data-testid="stAppViewContainer"] h1, 
        [data-testid="stAppViewContainer"] h2, 
        [data-testid="stAppViewContainer"] h3 { color: var(--main-text) !important; }
        .app-subtitle { color: #6b7280 !important; margin-top: -0.25rem; margin-bottom: 2rem; font-size: 0.95rem; }

        /* 2. TEXTING UI: Assistant Bubbles (Left-aligned, No Icons) */
        
        /* Step A: Obliterate the avatar and its container completely */
        [data-testid="stChatMessageAvatar"] { display: none !important; }
        [data-testid="stChatMessage"] > div:first-child { 
            display: none !important; 
            width: 0px !important; 
            margin: 0px !important; 
        }
        
        /* Step B: Transform the message block into a grey bubble */
        [data-testid="stChatMessage"] {
            background-color: #f0f4f9 !important; /* Soft Gemini Grey */
            border-radius: 20px 20px 20px 4px !important;
            padding: 15px 20px !important;
            margin-bottom: 15px !important;
            width: fit-content !important;
            max-width: 85% !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        }

        /* Step C: Force all text inside the bubble to be dark */
        [data-testid="stChatMessageContent"],
        [data-testid="stChatMessageContent"] p,
        [data-testid="stChatMessageContent"] li,
        [data-testid="stChatMessageContent"] span {
            color: var(--main-text) !important;
        }

        /* Table & Code block styling inside the assistant bubble */
        [data-testid="stChatMessageContent"] table { color: var(--main-text) !important; border-collapse: collapse; }
        [data-testid="stChatMessageContent"] th, [data-testid="stChatMessageContent"] td { border: 1px solid #d1d5db !important; }
        [data-testid="stChatMessageContent"] pre {
            background-color: #e5e7eb !important; 
            border: 1px solid var(--border-light) !important;
            border-radius: 12px !important;
        }
        [data-testid="stChatMessageContent"] code { color: #1f2937 !important; }

        /* 3. Top Navbar */
        header[data-testid="stHeader"] { background-color: var(--sidebar-bg) !important; }
        header[data-testid="stHeader"] button, header[data-testid="stHeader"] svg, header[data-testid="stHeader"] span {
            color: #ffffff !important; fill: #ffffff !important;
        }

        /* 4. Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--sidebar-bg) !important;
            border-right: 1px solid var(--sidebar-border) !important;
        }
        [data-testid="stSidebar"] * { color: var(--sidebar-text) !important; }
        
        [data-testid="stSidebar"] div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] div[data-testid="stTextInput"] input {
            background-color: #12182b !important;
            border: 1px solid var(--sidebar-border) !important;
            color: var(--sidebar-text) !important;
            border-radius: 8px;
            -webkit-text-fill-color: var(--sidebar-text) !important;
        }
        [data-testid="stSidebar"] ul[data-baseweb="menu"] { background-color: #12182b !important; }
        [data-testid="stSidebar"] ul[data-baseweb="menu"] li { color: var(--sidebar-text) !important; }

        /* Small Clear Chat Button */
        [data-testid="stSidebar"] div[data-testid="stButton"] button {
            background-color: transparent !important;
            border: 1px solid var(--sidebar-border) !important;
            color: #9ca3af !important;
            border-radius: 6px !important;
            padding: 2px 12px !important;
            font-size: 0.85rem !important;
            min-height: 32px !important;
            width: auto !important;
            display: inline-flex !important;
            margin-top: 10px !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
            border-color: #ef4444 !important; color: #ef4444 !important;
        }

        /* 5. Bottom Chat Area */
        [data-testid="stBottom"], [data-testid="stBottom"] > div {
            background-color: var(--main-bg) !important;
            border-top: none !important;
        }

        /* 6. Chat Input Box (White pill, Grey focus) */
        div[data-testid="stChatInputContainer"] {
            background-color: #ffffff !important;
            border: 1px solid #d1d5db !important;
            border-radius: 24px !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05) !important;
            padding: 5px 15px !important;
        }
        div[data-testid="stChatInputContainer"]:focus-within {
            border: 1px solid var(--focus-grey) !important; 
            box-shadow: 0 0 0 1px var(--focus-grey) !important;
            outline: none !important;
        }
        div[data-testid="stChatInputContainer"] textarea {
            color: var(--main-text) !important;
            -webkit-text-fill-color: var(--main-text) !important;
            background-color: transparent !important;
        }

        /* 7. FAQ Buttons */
        [data-testid="stAppViewContainer"] div[data-testid="stButton"] button {
            background-color: #f4f6f8 !important;
            border: none !important;
            border-radius: 20px !important;
            padding: 10px 20px !important;
        }
        [data-testid="stAppViewContainer"] div[data-testid="stButton"] button p {
            color: #1f1f1f !important; font-weight: 400 !important;
        }
        [data-testid="stAppViewContainer"] div[data-testid="stButton"] button:hover {
            background-color: #e8f0fe !important;
        }
        
        /* 8. Download Button */
        .stDownloadButton button {
            background-color: #ffffff !important; border: 1px solid #e5e7eb !important; border-radius: 8px !important;
            margin-top: 5px !important;
            margin-bottom: 20px !important;
        }
        .stDownloadButton button p { color: #111827 !important; }
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
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# --- SIDEBAR ---
with st.sidebar:
    st.text_input("Search", placeholder="Search chats (⇧⌘K)", label_visibility="collapsed")
    selected_model = st.selectbox("Model", list(AVAILABLE_MODELS.keys()), index=0, label_visibility="collapsed")
    st.divider()
    
    st.markdown("<h4 style='color: #ffffff; margin-bottom: 10px;'>Quick Filters</h4>", unsafe_allow_html=True)
    donor_status = st.selectbox("Donor Status", ["All", "Active", "Lapsed", "Prospect"])
    state_filter = st.selectbox("State", ["All", "VA", "NY", "CA", "TX"])
    st.divider()
    
    tracker_placeholder = st.empty()
    try:
        tracker_placeholder.markdown(st.session_state.tracker.format_sidebar())
    except Exception:
        pass 
        
    st.write("") 
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN UI ---
st.title(APP_TITLE)
st.markdown(f'<p class="app-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

# --- FAQ STARTER PROMPTS ---
if not st.session_state.messages:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏆 Who are the top 10 donors by lifetime donating?"):
            st.session_state.pending_prompt = "Who are the top 10 donors by lifetime donating?"
            st.rerun()
        if st.button("📊 Can you provide a summary of our donating statistics?"):
            st.session_state.pending_prompt = "Can you provide a summary of our donating statistics?"
            st.rerun()
    with col2:
        if st.button("⚠️ Show me lapsed donors who haven't donated since 2023"):
            st.session_state.pending_prompt = "Show me lapsed donors who haven't donated since 2023."
            st.rerun()
        if st.button("🗺️ Show me the geographic distribution of our donors"):
            st.session_state.pending_prompt = "Show me the geographic distribution of our donors."
            st.rerun()

# --- RENDER LOOP ---
for idx, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        # Right-aligned User Bubble
        st.markdown(
            f"""
            <div style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                <div style="background-color: #f4f6f8; color: #111827; padding: 12px 18px; border-radius: 20px 20px 4px 20px; max-width: 75%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    {message["content"]}
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        # The CSS above forces this st.chat_message to render as a tight, left-aligned grey bubble with no icon
        with st.chat_message("assistant"):
            st.markdown(message["content"])
            
        # Download button sits below the bubble
        csv_data = convert_to_csv(message["content"])
        is_csv = b',' in csv_data and b'\n' in csv_data
        file_ext = "csv" if is_csv else "txt"
        mime_type = "text/csv" if is_csv else "text/plain"
        
        st.download_button(
            label="📥 Download Data", data=csv_data,
            file_name=f"iasc_data_export_{idx}.{file_ext}", mime=mime_type, key=f"dl_btn_{idx}"
        )

# --- CHAT INPUT & FILE UPLOADER ---
supports_chat_attachments = "accept_file" in inspect.signature(st.chat_input).parameters

active_prompt = None
uploaded_file = None

if supports_chat_attachments:
    prompt_input = st.chat_input("Ask about your donor community...", accept_file=True)
    if prompt_input:
        if hasattr(prompt_input, "text"):
            active_prompt = prompt_input.text
            uploaded_file = prompt_input.files[0] if prompt_input.files else None
        elif isinstance(prompt_input, dict):
            active_prompt = prompt_input.get("text", "")
            files = prompt_input.get("files", [])
            uploaded_file = files[0] if files else None
        else:
            active_prompt = str(prompt_input)
else:
    with st.container():
        uploaded_file = st.file_uploader("📎 Attach a donor report (CSV/PDF)", type=['csv', 'pdf', 'txt'])
        prompt_input = st.chat_input("Ask about your donor community...")
        if prompt_input:
            active_prompt = prompt_input
            if not active_prompt and uploaded_file:
                active_prompt = f"Please analyze this attached file: {uploaded_file.name}"

if st.session_state.pending_prompt:
    active_prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

# --- EXECUTE CHAT ---
if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    
    # Draw user bubble immediately
    st.markdown(
        f"""
        <div style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
            <div style="background-color: #f4f6f8; color: #111827; padding: 12px 18px; border-radius: 20px 20px 4px 20px; max-width: 75%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                {active_prompt}
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )

    # Spinner is detached from the chat container so it looks like a typing indicator
    with st.status("Consulting IASC records...", expanded=True) as status:
        
        # Hardened instructions banning the use of the word "fields" entirely
        hidden_instruction = "\n\n[CRITICAL INSTRUCTIONS: 1. Do NOT output 'Tool Call:', 'Results:', or raw JSON. 2. NEVER use the words 'fields', 'columns', 'SQL', or explain your database schema. Do not list internal variable names. 3. Present the final answer conversationally as a human analyst.]"
        enhanced_prompt = active_prompt + hidden_instruction

        raw_response, usage = get_response(
            user_message=enhanced_prompt,
            conversation_history=st.session_state.messages[:-1],
            model=selected_model,
            session_tracker=st.session_state.tracker,
            attachment=uploaded_file
        )
        
        clean_response_text = scrub_tool_calls(raw_response)
        status.update(label="Complete!", state="complete", expanded=False)

    # Save to history and rerun (rerun triggers the new CSS-styled assistant bubble)
    st.session_state.messages.append({"role": "assistant", "content": clean_response_text})
    st.session_state.tracker.format_sidebar()
    st.rerun()

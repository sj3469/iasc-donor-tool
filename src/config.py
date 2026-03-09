import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for the IASC and The Hedgehog Review"

# Align with your GitHub 'data' folder structure
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "donors.db"

# Secure Key Retrieval
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

# Added both 2.5 and 2.0. If 2.5 fails, we can easily toggle to 2.0 in the sidebar.
AVAILABLE_MODELS = {
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.0-flash": "Gemini 2.0 Flash (Stable Fallback)",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
}
DEFAULT_MODEL = "gemini-2.5-flash"

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

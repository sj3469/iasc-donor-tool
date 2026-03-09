import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for the IASC and The Hedgehog Review"

# Align with your GitHub data folder
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "donors.db"

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

AVAILABLE_MODELS = {
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
}
DEFAULT_MODEL = "gemini-2.0-flash"

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

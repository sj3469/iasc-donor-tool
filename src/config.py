import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Variables for the UI text
APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for the IASC and The Hedgehog Review"

# Points directly to the files in your 'src' folder
BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "mock_dataset3.csv"
DB_PATH = BASE_DIR / "donors.db"

# Pulls from Streamlit Secrets Dashboard
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

AVAILABLE_MODELS = {
    "gemini-2.0-flash": "Gemini 2.0 Flash (Fastest)",
    "gemini-1.5-pro": "Gemini 1.5 Pro (Most Capable)",
}
DEFAULT_MODEL = "gemini-2.0-flash"

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

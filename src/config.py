import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for the IASC and The Hedgehog Review"

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "mock_dataset3.csv"
DB_PATH = BASE_DIR / "donors.db"

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

AVAILABLE_MODELS = {
    "gemini-2.5-flash": "Gemini 2.5 Flash (Fastest)",
    "gemini-2.5-pro": "Gemini 2.5 Pro (Most Capable)",
}

DEFAULT_MODEL = "gemini-2.5-flash"

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

# 1. Load local .env for local testing
load_dotenv()

# 2. Key Title & Text
APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for the IASC and The Hedgehog Review"

# 3. Path Configurations
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "donors.db"

# 4. API Key Resolution (Web vs Local)
# This looks in Streamlit Secrets first, then your local environment.
# KEEP THESE LABELS EXACTLY AS WRITTEN IN QUOTES.
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

# 5. Model Settings
AVAILABLE_MODELS = {
    "gemini-2.0-flash": "Gemini 2.0 Flash (Fastest)",
    "gemini-1.5-pro": "Gemini 1.5 Pro (Most Capable)",
}
DEFAULT_MODEL = "gemini-2.0-flash"

# 6. Inject keys into environment correctly
# This is where the magic happens. The labels in quotes stay the same.
if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = AIzaSyAwNhYgYsyPfn15l4I8gF8T6Z-ukMfpaCA

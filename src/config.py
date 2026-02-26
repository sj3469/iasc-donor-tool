"""
Configuration and constants for the IASC donor analytics tool.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (for local development)
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
DB_PATH = DATA_DIR / "donors.db"

# API configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model configuration
DEFAULT_MODEL = "claude-sonnet-4-20250514"
AVAILABLE_MODELS = {
    "claude-sonnet-4-20250514": "Sonnet (recommended)",
    "claude-haiku-4-5-20251001": "Haiku (faster, cheaper)",
}

# Tool use limits
MAX_TOOL_CALLS_PER_TURN = 5  # prevent infinite loops
MAX_RESULTS_PER_QUERY = 20   # default limit for search results

# UI configuration
APP_TITLE = "IASC Donor Analytics"
APP_SUBTITLE = "AI-powered donor intelligence for The Hedgehog Review"

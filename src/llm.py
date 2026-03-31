import os
import re
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Callable

try:
    from google import genai
except Exception:
    genai = None

from queries import (
    search_donors,
    get_donor_detail,
    get_summary_statistics,
    get_geographic_distribution,
    get_lapsed_donors,
    get_prospects_by_potential,
    plan_fundraising_trip,
)

from prompts import build_system_prompt, needs_knowledge_base

STATE_NAME_TO_ABBR = {
    "virginia": "VA", "new york": "NY", "district of columbia": "DC",
    "washington dc": "DC", "maryland": "MD", "massachusetts": "MA",
    "illinois": "IL", "california": "CA", "texas": "TX", "florida": "FL",
}
VALID_STATE_ABBRS = set(STATE_NAME_TO_ABBR.values())

def _safe_log_usage(session_tracker: Any, model: str, usage: Any, question: str = "") -> None:
    if not session_tracker or not hasattr(session_tracker, "log_call"):
        return
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    session_tracker.log_call(model=model, input_tokens=input_tokens, output_tokens=output_tokens, question=question)

def _zero_usage():
    return SimpleNamespace(prompt_token_count=0, candidates_token_count=0)

def _fmt_currency(value: Any) -> str:
    try: return f"${float(value):,.2f}" if value is not None else "N/A"
    except: return "N/A"

def _extract_zip(text: str) -> Optional[str]:
    match = re.search(r"\b\d{5}\b", text)
    return match.group(0) if match else None

def _extract_contact_id(text: str) -> Optional[str]:
    match = re.search(r"\b003[A-Za-z0-9]{15}\b", text)
    return match.group(0) if match else None

def _extract_state(text: str) -> Optional[str]:
    for abbr in VALID_STATE_ABBRS:
        if re.search(rf"\b{abbr}\b", text.upper()): return abbr
    for name, abbr in STATE_NAME_TO_ABBR.items():
        if name in text.lower(): return abbr
    return None

def _is_complex_query(text: str) -> bool:
    """Detects if the query has modifiers that the hard-coded regex paths can't handle."""
    complex_indicators = [
        "since", "after", "before", "202", "201", "greater than", 
        "more than", "less than", "above", "below", "increased", "decreased"
    ]
    return any(indicator in text.lower() for indicator in complex_indicators)

def _format_donor_list(title: str, result: dict) -> str:
    rows = result.get("results", [])
    if not rows: return f"{title}\n\nNo matching donors found."
    lines = [f"### {title}"]
    for r in rows[:10]:
        name = f"{r.get('first_name','')} {r.get('last_name','')}".strip() or r.get('contact_id')
        lines.append(f"- **{name}** | {r.get('city')}, {r.get('state')} | Total: {_fmt_currency(r.get('total_gifts'))} | Status: {r.get('donor_status')}")
    return "\n".join(lines)

def _handle_direct_query(user_message: str) -> Optional[str]:
    text = user_message.lower().strip()
    
    # BUG FIX: If query is complex (contains dates/amounts), bypass direct path and use LLM
    if _is_complex_query(text):
        return None

    contact_id = _extract_contact_id(user_message)
    if contact_id:
        from llm import _format_donor_detail # Local helper
        return _format_donor_detail(get_donor_detail(contact_id))

    zip_code = _extract_zip(user_message)
    state = _extract_state(user_message)

    if "lapsed" in text:
        return _format_donor_list(f"Lapsed Donors {f'in {state}' if state else ''}", 
                                  search_donors(state=state, donor_status="lapsed") if state else get_lapsed_donors())
    
    if "summary" in text and "overall" in text:
        from llm import _format_summary
        return _format_summary(get_summary_statistics())

    return None

def get_response(user_message, conversation_history, model, session_tracker, **kwargs):
    direct_answer = _handle_direct_query(user_message)
    if direct_answer:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage, question=user_message)
        return direct_answer, usage

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    include_knowledge = needs_knowledge_base(user_message)
    system_instruction = build_system_prompt(include_knowledge=include_knowledge)

    response = client.models.generate_content(
        model=model,
        contents=[system_instruction, user_message],
    )
    
    usage = getattr(response, "usage_metadata", _zero_usage())
    _safe_log_usage(session_tracker, model, usage, question=user_message)
    return response.text, usage

# (Note: Keeping formatting helpers like _format_donor_detail and _format_summary as they were in your original)
def _format_donor_detail(result: dict) -> str:
    rows = result.get("results", [])
    if not rows: return "No donor found."
    r = rows[0]
    return f"**Donor Detail: {r.get('first_name')} {r.get('last_name')}**\n- ID: {r.get('contact_id')}\n- Status: {r.get('donor_status')}\n- Total Gifts: {_fmt_currency(r.get('total_gifts'))}\n- Notes: {r.get('notes')}"

def _format_summary(result: dict) -> str:
    rows = result.get("results", [])
    if not rows: return "No stats."
    r = rows[0]
    return f"**Database Summary**\n- Total Donors: {r.get('donor_count')}\n- Total Giving: {_fmt_currency(r.get('total_giving'))}"

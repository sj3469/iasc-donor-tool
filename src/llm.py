import os
import re
import time
from datetime import datetime
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Callable

from google import genai
from google.genai import types, errors

from prompts import build_system_prompt, needs_knowledge_base
from queries import search_donors

try:
    from usage_store import log_api_call
except Exception:
    log_api_call = None


STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}

ABBREV_TO_NAME = {v: k.title() for k, v in STATE_MAP.items()}


def _flatten_system_prompt(raw_prompt: Any) -> str:
    if isinstance(raw_prompt, list):
        return " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in raw_prompt
        )
    return str(raw_prompt)


def _build_prompt_content(
    user_message: str,
    conversation_history: List[Dict[str, str]],
) -> str:
    parts = []

    if conversation_history:
        parts.append("Conversation so far:")
        for message in conversation_history[-12:]:
            role = message.get("role", "user").capitalize()
            content = message.get("content", "")
            if content:
                parts.append(f"{role}: {content}")

    parts.append(f"User: {user_message}")
    return "\n".join(parts)


def _extract_response_text(response: Any) -> str:
    try:
        text = getattr(response, "text", None)
        if text and str(text).strip():
            return str(text).strip()
    except Exception:
        pass

    texts = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text and str(part_text).strip():
                texts.append(str(part_text).strip())

    if texts:
        return "\n".join(texts)

    return "I couldn't generate a text response."


def _normalize_state(value: str) -> Optional[str]:
    if not value:
        return None

    cleaned = value.strip().lower()
    if cleaned in STATE_MAP:
        return STATE_MAP[cleaned]

    compact = re.sub(r"[^A-Za-z]", "", value).upper()
    if len(compact) == 2 and compact in ABBREV_TO_NAME:
        return compact

    return None


def _state_display(code: str) -> str:
    return ABBREV_TO_NAME.get(code, code)


def _extract_state_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    lowered = text.lower().strip()

    direct = _normalize_state(lowered)
    if direct:
        return direct

    for full_name, abbr in sorted(STATE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(full_name)}\b", lowered):
            return abbr

    tokens = re.findall(r"\b[A-Za-z]{2}\b", text.upper())
    for token in tokens:
        if token in ABBREV_TO_NAME:
            return token

    return None


def _assistant_just_asked_for_state(conversation_history: List[Dict[str, str]]) -> bool:
    if not conversation_history:
        return False

    last = conversation_history[-1]
    if last.get("role") != "assistant":
        return False

    content = (last.get("content") or "").lower()
    return "which state" in content or "what state" in content


def _is_top_donors_request(text: str) -> bool:
    lowered = text.lower()
    return (
        ("top donor" in lowered)
        or ("top donors" in lowered)
        or ("show donors" in lowered)
        or ("show top donors" in lowered)
        or ("list donors" in lowered)
    )


def _format_donor_results(result: dict, state_code: str) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return f"I couldn't find any donors in {_state_display(state_code)}."

    lines = [f"Top donors in {_state_display(state_code)}:"]
    for i, row in enumerate(rows[:10], start=1):
        first_name = row.get("first_name", "") or ""
        last_name = row.get("last_name", "") or ""
        full_name = f"{first_name} {last_name}".strip() or "Unknown donor"
        city = row.get("city") or "Unknown city"
        state = row.get("state") or state_code
        total_gifts = row.get("total_gifts")
        last_gift_date = row.get("last_gift_date") or "Unknown"
        donor_status = row.get("donor_status") or "Unknown"
        wealth_score = row.get("wealth_score")

        total_gifts_str = f"${total_gifts:,.2f}" if isinstance(total_gifts, (int, float)) else str(total_gifts or "$0.00")
        wealth_str = f", wealth score {wealth_score}" if wealth_score is not None else ""

        lines.append(
            f"{i}. {full_name} — {city}, {state}; total giving {total_gifts_str}; "
            f"last gift {last_gift_date}; status {donor_status}{wealth_str}."
        )

    return "\n".join(lines)


def _maybe_handle_direct_query(
    user_message: str,
    conversation_history: List[Dict[str, str]],
) -> Optional[str]:
    state_code = _extract_state_from_text(user_message)

    if _assistant_just_asked_for_state(conversation_history) and state_code:
        result = search_donors(state=state_code, sort_by="total_gifts", sort_order="desc", limit=10)
        return _format_donor_results(result, state_code)

    if _is_top_donors_request(user_message):
        if state_code:
            result = search_donors(state=state_code, sort_by="total_gifts", sort_order="desc", limit=10)
            return _format_donor_results(result, state_code)
        return "Which state are you interested in?"

    return None


def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None,
) -> tuple[str, Any]:
    start_time = time.perf_counter()

    direct_response = _maybe_handle_direct_query(user_message, conversation_history)
    if direct_response is not None:
        latency_ms = (time.perf_counter() - start_time) * 1000
        usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=0)

        session_tracker.log_call(
            model=model,
            input_tokens=0,
            output_tokens=0,
            had_tool_use=True,
            latency_ms=latency_ms,
            question=user_message,
        )

        if log_api_call:
            try:
                log_api_call(
                    timestamp=datetime.now(),
                    model=model,
                    input_tokens=0,
                    output_tokens=0,
                    had_tool_use=True,
                    latency_ms=latency_ms,
                    question=user_message,
                    session_id=st_session_id,
                )
            except Exception:
                pass

        return direct_response, usage

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    include_knowledge = needs_knowledge_base(user_message)
    raw_prompt = build_system_prompt(include_knowledge=include_knowledge)
    system_instruction_text = _flatten_system_prompt(raw_prompt)
    prompt_content = _build_prompt_content(user_message, conversation_history)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_text,
                temperature=0.2,
            ),
        )
    except errors.APIError as e:
        raise RuntimeError(f"Gemini API error: status={e.code} message={e}") from e

    latency_ms = (time.perf_counter() - start_time) * 1000
    usage = response.usage_metadata

    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    response_text = _extract_response_text(response)

    session_tracker.log_call(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        had_tool_use=False,
        latency_ms=latency_ms,
        question=user_message,
    )

    if log_api_call:
        try:
            log_api_call(
                timestamp=datetime.now(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                had_tool_use=False,
                latency_ms=latency_ms,
                question=user_message,
                session_id=st_session_id,
            )
        except Exception:
            pass

    return response_text, usage

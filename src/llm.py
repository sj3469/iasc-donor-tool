import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

from google import genai
from google.genai import types, errors

from prompts import build_system_prompt, needs_knowledge_base
from queries import (
    search_donors,
    get_donor_detail,
    get_summary_statistics,
    get_geographic_distribution,
    get_lapsed_donors,
    get_prospects_by_potential,
    plan_fundraising_trip,
)
from usage_store import log_api_call


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


def _flatten_system_prompt(raw_prompt: Any) -> str:
    if isinstance(raw_prompt, list):
        return " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in raw_prompt
        )
    return str(raw_prompt)


def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None,
) -> tuple[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    include_knowledge = needs_knowledge_base(user_message)
    raw_prompt = build_system_prompt(include_knowledge=include_knowledge)
    system_instruction_text = _flatten_system_prompt(raw_prompt)

    prompt_content = _build_prompt_content(user_message, conversation_history)

    tools = [
        search_donors,
        get_donor_detail,
        get_summary_statistics,
        get_geographic_distribution,
        get_lapsed_donors,
        get_prospects_by_potential,
        plan_fundraising_trip,
    ]

    start_time = time.perf_counter()

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_text,
                tools=tools,
                temperature=0.2,
            ),
        )
    except errors.APIError as e:
        raise RuntimeError(f"Gemini API error: status={e.code} message={e}") from e

    latency_ms = (time.perf_counter() - start_time) * 1000
    usage = response.usage_metadata

    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    response_text = response.text if getattr(response, "text", None) else "No response generated."

    session_tracker.log_call(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        question=user_message,
    )

    try:
        log_api_call(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            question=user_message,
            session_id=st_session_id,
        )
    except Exception:
        pass

    return response_text, usage


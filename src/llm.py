import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types

from prompts import build_system_prompt


def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None,
) -> tuple[str, Any]:

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    raw_prompt = build_system_prompt()
    if isinstance(raw_prompt, list):
        system_instruction_text = " ".join(
            [p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_prompt]
        )
    else:
        system_instruction_text = str(raw_prompt)

    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_text,
            temperature=0.2,
        ),
    )

    usage = response.usage_metadata
    session_tracker.log_call(
        model=model,
        input_tokens=getattr(usage, "prompt_token_count", 0),
        output_tokens=getattr(usage, "candidates_token_count", 0),
    )

    return response.text, usage


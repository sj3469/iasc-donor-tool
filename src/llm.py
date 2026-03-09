import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types
from queries import (
    search_donors, get_donor_detail, get_summary_statistics,
    get_geographic_distribution, get_lapsed_donors,
    get_prospects_by_potential, plan_fundraising_trip
)
from prompts import build_system_prompt

def get_response(
    user_message: str, conversation_history: List[Dict[str, str]],
    model: str, session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    attachment: Optional[Any] = None
) -> tuple[str, Any]:
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Define Tools
    tools = [search_donors, get_donor_detail, get_summary_statistics,
             get_geographic_distribution, get_lapsed_donors,
             get_prospects_by_potential, plan_fundraising_trip]

    # Convert Prompt to String
    raw_prompt = build_system_prompt()
    system_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_prompt]) if isinstance(raw_prompt, list) else str(raw_prompt)

    prompt_content = [user_message]
    if attachment:
        # Note: In production, save uploader to temp file first
        prompt_content.append(attachment.getvalue().decode("utf-8") if attachment.type == 'text/csv' else "File attached")

    # FIXED: Simplified config to prevent ClientError
    response = client.models.generate_content(
        model=model,
        contents=prompt_content,
        config=types.GenerateContentConfig(
            system_instruction=system_text,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig()
        )
    )

    usage = response.usage_metadata
    session_tracker.log_call(model=model, input_tokens=usage.prompt_token_count, output_tokens=usage.candidates_token_count)
    return response.text, usage

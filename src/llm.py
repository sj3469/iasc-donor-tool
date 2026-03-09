import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types

# Import database tools from the local src folder
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
    st_session_id: Optional[str] = None, attachment: Optional[Any] = None
) -> tuple[str, Any]:
    
    # Initialize the Gemini Client
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    tools = [search_donors, get_donor_detail, get_summary_statistics,
             get_geographic_distribution, get_lapsed_donors,
             get_prospects_by_potential, plan_fundraising_trip]

    # Clean the system prompt to avoid validation errors
    raw_prompt = build_system_prompt()
    if isinstance(raw_prompt, list):
        system_instruction_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_prompt])
    else:
        system_instruction_text = str(raw_prompt)

    prompt_content = [user_message]
    
    # Execute with Automatic Function Calling
    response = client.models.generate_content(
        model=model,
        contents=prompt_content,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_text,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig()
        )
    )

    usage = response.usage_metadata
    session_tracker.log_call(model=model, input_tokens=usage.prompt_token_count, output_tokens=usage.candidates_token_count)

    return response.text, usage

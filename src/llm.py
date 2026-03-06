"""
IASC Donor Analytics — LLM Integration Layer.
Integrated with Gemini Function Calling for queries.py tools.
"""

import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types

# Import your actual tool functions
from queries import (
    search_donors, 
    get_donor_detail, 
    get_summary_statistics, 
    get_geographic_distribution,
    get_lapsed_donors,
    get_prospects_by_potential,
    plan_fundraising_trip
)
from config import AVAILABLE_MODELS
from prompts import build_system_prompt

def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None
) -> tuple[str, Any]:
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    # 1. Define the Toolset for Gemini
    # We pass your Python functions directly to the model
    tools = [
        search_donors, get_donor_detail, get_summary_statistics,
        get_geographic_distribution, get_lapsed_donors,
        get_prospects_by_potential, plan_fundraising_trip
    ]

    # 2. Prepare content (including photo/file if present)
    prompt_content = [user_message]
    if attachment:
        if progress_callback: progress_callback(f"Analyzing {attachment.name}...")
        file_handle = client.files.upload(file=attachment)
        prompt_content.append(file_handle)

    # 3. Execute with Automatic Function Calling
    # This allows Gemini to call your queries.py functions, get data, and then speak.
    if progress_callback: progress_callback("Consulting IASC database...")
    
    response = client.models.generate_content(
        model=model,
        contents=prompt_content,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(),
            tools=tools,
            # 'auto' allows the model to decide when to use a tool
            automatic_function_calling=types.AutomaticFunctionCallingConfig(max_remote_calls=5)
        )
    )

    # 4. Log Usage
    usage = response.usage_metadata
    session_tracker.log_call(
        model=model,
        input_tokens=usage.prompt_token_count,
        output_tokens=usage.candidates_token_count
    )

    return response.text, usage

import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types, errors

# Import tools from queries.py
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
    
    # Register tools
    tools = [search_donors, get_donor_detail, get_summary_statistics,
             get_geographic_distribution, get_lapsed_donors,
             get_prospects_by_potential, plan_fundraising_trip]

    # Clean system instructions
    raw_prompt = build_system_prompt()
    system_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_prompt]) if isinstance(raw_prompt, list) else str(raw_prompt)

    prompt_content = [user_message]
    if attachment:
        file_content = attachment.getvalue().decode("utf-8", errors="ignore")
        prompt_content.append(f"\n\nAdditional File Context:\n{file_content}")

    # --- THE CATCH AND REVEAL FIX ---
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_text if system_text else None,
                tools=tools,
                # Using a dictionary format is more stable across SDK versions
                automatic_function_calling={"disable": False}
            )
        )

        usage = response.usage_metadata
        session_tracker.log_call(model=model, input_tokens=usage.prompt_token_count, output_tokens=usage.candidates_token_count)
        return response.text, usage

    # If Google's API rejects the request, we print the exact reason in the chat
    except errors.ClientError as e:
        error_details = getattr(e, 'response_json', str(e))
        return f"🚨 **Google API Error:**\n```json\n{error_details}\n```", None
    except Exception as e:
        return f"🚨 **Unexpected Error:**\n{str(e)}", None

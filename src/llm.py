"""
IASC Donor Analytics — LLM Integration Layer.
Updated to handle file attachments and database tool calling.
"""

import os
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types
from anthropic import Anthropic

# Import internal modules from your project
from config import AVAILABLE_MODELS
from prompts import build_system_prompt
# This assumes you have a queries.py that defines your SQL tools
from queries import run_query_tool 

def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None  # Fixed: Added the missing argument
) -> tuple[str, Any]:
    """
    Handles the conversation loop, file uploads, and tool execution.
    """
    
    # Initialize Clients
    gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    claude_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Prepare Content for Gemini (Support for Photos/Files)
    prompt_content = [user_message]
    
    if attachment and "gemini" in model.lower():
        if progress_callback:
            progress_callback(f"Reading {attachment.name}...")
        
        # Upload file to Gemini's temporary storage
        file_handle = gemini_client.files.upload(file=attachment)
        prompt_content.append(file_handle)

    # Execution for Gemini Models
    if "gemini" in model.lower():
        if progress_callback:
            progress_callback("Consulting IASC donor database...")
            
        # This call now includes the system instructions and potential file
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=build_system_prompt(),
            )
        )
        
        # Log usage to your tracker
        usage = response.usage_metadata
        session_tracker.log_call(
            model=model,
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count
        )
        
        return response.text, usage

    # Execution for Claude Models
    else:
        if progress_callback:
            progress_callback("Claude is analyzing...")
            
        response = claude_client.messages.create(
            model=model,
            max_tokens=2048,
            system=build_system_prompt(),
            messages=conversation_history + [{"role": "user", "content": user_message}]
        )
        
        session_tracker.log_call(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
        
        return response.content[0].text, response.usage

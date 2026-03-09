"""
Token usage tracker for the IASC donor analytics tool.
Tracks per-response and per-session token usage and estimated costs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# Updated to match the models available in your config.py
MODEL_PRICING = {
    "gemini-2.0-flash": {
        "input_per_mtok": 0.10,
        "output_per_mtok": 0.40,
        "display_name": "Gemini 2.0 Flash",
    },
    "gemini-1.5-pro": {
        "input_per_mtok": 1.25,
        "output_per_mtok": 10.00,
        "display_name": "Gemini 1.5 Pro",
    },
    "default": {
        "input_per_mtok": 0.0,
        "output_per_mtok": 0.0,
        "display_name": "Unknown Model",
    },
}

@dataclass
class APICall:
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    model: str

@dataclass
class ResponseUsage:
    question: str
    calls: List[APICall] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    def estimated_cost(self, model: Optional[str] = None) -> float:
        total_cost = 0.0
        for call in self.calls:
            model_key = model or call.model
            pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["default"])
            total_cost += (call.input_tokens / 1_000_000) * pricing["input_per_mtok"]
            total_cost += (call.output_tokens / 1_000_000) * pricing["output_per_mtok"]
        return total_cost

# Renamed to SessionTokenTracker to fix the ImportError in app.py
class SessionTokenTracker:
    def __init__(self):
        self.responses: List[ResponseUsage] = []

    def log_call(self, model: str, input_tokens: int, output_tokens: int, question: str = "") -> None:
        response_usage = ResponseUsage(question=question)
        response_usage.calls.append(
            APICall(
                timestamp=datetime.now(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model
            )
        )
        self.responses.append(response_usage)

    @property
    def total_input_tokens(self) -> int:
        return sum(r.total_input_tokens for r in self.responses)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.total_output_tokens for r in self.responses)

    @property
    def total_cost(self) -> float:
        return sum(r.estimated_cost() for r in self.responses)

    def format_sidebar(self) -> str:
        return (
            f"**Session Usage**\n\n"
            f"- Questions: {len(self.responses)}\n"
            f"- Input Tokens: {self.total_input_tokens:,}\n"
            f"- Output Tokens: {self.total_output_tokens:,}\n"
            f"- Estimated Cost: ${self.total_cost:.4f}"
        )

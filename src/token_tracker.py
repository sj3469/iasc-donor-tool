"""
Token usage tracker for the IASC donor analytics tool.

Tracks per-response and per-session token usage and estimated costs,
including prompt caching savings. Designed to be displayed inline with
each response and in the Streamlit sidebar.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


# Pricing placeholders.
# These are not accurate for Gemini, but they prevent crashes and allow display.
MODEL_PRICING = {
    "gemini-2.0-flash": {
        "input_per_mtok": 0.0,
        "output_per_mtok": 0.0,
        "display_name": "Gemini 2.0 Flash",
    },
    "gemini-1.5-pro": {
        "input_per_mtok": 0.0,
        "output_per_mtok": 0.0,
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
    """A single API call within a response."""
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    model: str
    had_tool_use: bool = False
    latency_ms: float = 0.0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class ResponseUsage:
    """Aggregated usage for one user question."""
    question: str
    calls: List[APICall] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def num_api_calls(self) -> int:
        return len(self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    @property
    def total_cache_read_tokens(self) -> int:
        return sum(c.cache_read_input_tokens for c in self.calls)

    @property
    def total_cache_creation_tokens(self) -> int:
        return sum(c.cache_creation_input_tokens for c in self.calls)

    def estimated_cost(self, model: str) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        base_rate = pricing["input_per_mtok"]
        output_rate = pricing["output_per_mtok"]

        total_cost = 0.0
        for call in self.calls:
            regular_input = (
                call.input_tokens
                - call.cache_creation_input_tokens
                - call.cache_read_input_tokens
            )
            total_cost += (regular_input / 1_000_000) * base_rate
            total_cost += (call.cache_creation_input_tokens / 1_000_000) * base_rate * 1.25
            total_cost += (call.cache_read_input_tokens / 1_000_000) * base_rate * 0.1
            total_cost += (call.output_tokens / 1_000_000) * output_rate

        return total_cost

    def format_inline(self, model: str) -> str:
        cost = self.estimated_cost(model)
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        model_name = pricing["display_name"]
        cache_info = ""
        if self.total_cache_read_tokens > 0:
            cache_info = f" | {self.total_cache_read_tokens:,} cached"

        return (
            f"Stats: {model_name} | {self.num_api_calls} API call(s) | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens"
            f"{cache_info} | "
            f"${cost:.4f} | {self.total_latency_ms:.0f}ms"
        )


class SessionTracker:
    """Tracks all API usage within a Streamlit session."""

    def __init__(self):
        self.responses: List[ResponseUsage] = []

    def log_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        had_tool_use: bool = False,
        latency_ms: float = 0.0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        question: str = "",
    ) -> None:
        response_usage = ResponseUsage(question=question)
        response_usage.calls.append(
            APICall(
                timestamp=datetime.now(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model,
                had_tool_use=had_tool_use,
                latency_ms=latency_ms,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
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
        if not self.responses:
            return 0.0

        total = 0.0
        for response in self.responses:
            if response.calls:
                model = response.calls[-1].model
            else:
                model = "default"
            total += response.estimated_cost(model)
        return total

    @property
    def total_api_calls(self) -> int:
        return sum(r.num_api_calls for r in self.responses)

    def format_sidebar(self) -> str:
        return (
            f"**Session usage**\n\n"
            f"- Questions asked: {len(self.responses)}\n"
            f"- API calls: {self.total_api_calls}\n"
            f"- Input tokens: {self.total_input_tokens:,}\n"
            f"- Output tokens: {self.total_output_tokens:,}\n"
            f"- Estimated cost: ${self.total_cost:.4f}\n"
        )

"""
Token usage tracker for the IASC donor analytics tool.
Tracks per-response and per-session token usage and estimated costs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


MODEL_PRICING = {
    "gemini-2.5-flash": {
        "input_per_mtok": 0.30,
        "output_per_mtok": 2.50,
        "cache_per_mtok": 0.03,
        "display_name": "Gemini 2.5 Flash",
    },
    "gemini-2.5-pro": {
        "input_per_mtok": 1.25,
        "output_per_mtok": 10.00,
        "cache_per_mtok": 0.125,
        "display_name": "Gemini 2.5 Pro",
    },
    "default": {
        "input_per_mtok": 0.0,
        "output_per_mtok": 0.0,
        "cache_per_mtok": 0.0,
        "display_name": "Unknown Model",
    },
}


@dataclass
class APICall:
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

    def estimated_cost(self, model: Optional[str] = None) -> float:
        total_cost = 0.0

        for call in self.calls:
            model_key = model or call.model
            pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["default"])

            input_rate = pricing["input_per_mtok"]
            output_rate = pricing["output_per_mtok"]
            cache_rate = pricing["cache_per_mtok"]

            cache_tokens = (call.cache_creation_input_tokens or 0) + (call.cache_read_input_tokens or 0)
            regular_input = max(0, call.input_tokens - cache_tokens)

            total_cost += (regular_input / 1_000_000) * input_rate
            total_cost += (cache_tokens / 1_000_000) * cache_rate
            total_cost += (call.output_tokens / 1_000_000) * output_rate

        return total_cost

    def format_inline(self, model: Optional[str] = None) -> str:
        model_key = model or (self.calls[-1].model if self.calls else "default")
        pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["default"])
        model_name = pricing["display_name"]
        cost = self.estimated_cost(model_key)

        cache_info = ""
        if self.total_cache_read_tokens > 0 or self.total_cache_creation_tokens > 0:
            total_cached = self.total_cache_read_tokens + self.total_cache_creation_tokens
            cache_info = f" | {total_cached:,} cached"

        return (
            f"Stats: {model_name} | {self.num_api_calls} API call(s) | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens"
            f"{cache_info} | ${cost:.4f} | {self.total_latency_ms:.0f}ms"
        )


class SessionTracker:
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
        return sum(r.estimated_cost() for r in self.responses)

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

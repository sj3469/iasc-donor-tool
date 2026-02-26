# IASC Donor Tool: token optimization instructions

These instructions are for Claude Code to apply to the project at `/Users/gkossinets/github/iasc-donor-tool`. Apply them in the order listed. After each patch, run the existing tests (`pytest tests/test_queries.py`) to confirm nothing broke.

---

## Patch 1: conditional knowledge base injection (prompts.py)

### Problem

The full knowledge base (~5,000 tokens) is injected into every API call via the system prompt, even for simple data queries like "How many donors in NYC?" This wastes tokens and contributes to 429 rate limit errors (the org limit is 30,000 input tokens per minute).

### Changes to `src/prompts.py`

Add a keyword-based classifier that decides whether the knowledge base is needed. Modify `build_system_prompt()` to accept a boolean flag.

Replace the current `build_system_prompt()` function and add `needs_knowledge_base()`:

```python
# Add near the top, after imports

KNOWLEDGE_TRIGGER_KEYWORDS = [
    "best practice", "strategy", "how to", "recommend", "advice",
    "approach", "re-engage", "re-engagement", "cultivate", "cultivation",
    "retention", "pipeline", "moves management", "major gift",
    "prospect research", "donor pyramid", "rfm", "wealth screen",
    "center-out", "stewardship", "solicitation", "annual fund",
    "capital campaign", "planned giving", "donor lifecycle",
    "engagement strategy", "outreach plan", "thank", "acknowledge",
]


def needs_knowledge_base(user_message: str) -> bool:
    """Check whether the user's question likely needs fundraising best-practice context.

    Uses simple keyword matching. This avoids an extra API call; a false negative
    just means the response won't reference best practices (the user can ask a
    follow-up), while a false positive only costs ~5K extra input tokens.
    """
    msg_lower = user_message.lower()
    return any(kw in msg_lower for kw in KNOWLEDGE_TRIGGER_KEYWORDS)


def build_system_prompt(include_knowledge: bool = False) -> str:
    """Assemble the full system prompt: base instructions + schema + optional knowledge base.

    Args:
        include_knowledge: If True, append the fundraising knowledge base documents.
                          Set this based on needs_knowledge_base() for the current query.
    """
    prompt = BASE_SYSTEM_PROMPT + DB_SCHEMA_SUMMARY
    if include_knowledge:
        kb_content = load_knowledge_base()
        prompt += kb_content
    else:
        prompt += (
            "\n\nNote: A fundraising best-practices knowledge base is available. "
            "If the user asks about strategy, best practices, or 'how to' questions "
            "about fundraising, let them know you can provide guidance and ask them "
            "to rephrase if needed.\n"
        )
    return prompt
```

Delete the old `build_system_prompt()` (the one with no parameters that always calls `load_knowledge_base()`).

### Why the fallback note matters

When the KB is not loaded, Claude still needs to know it *exists* so it can say "I can help with that; could you ask again specifically about best practices?" rather than hallucinating advice. The fallback note is ~50 tokens instead of ~5,000.

---

## Patch 2: use knowledge base flag in llm.py

### Changes to `src/llm.py`

In the `get_response()` function:

1. Add a `progress_callback` parameter.
2. Import `needs_knowledge_base` from prompts.
3. Build the system prompt conditionally.
4. Add retry logic for 429 errors.
5. Report progress at each step.

Replace the entire `get_response()` function with:

```python
from typing import Optional, Callable
from prompts import build_system_prompt, needs_knowledge_base


def _summarize_tool_params(tool_name: str, params: dict) -> str:
    """Create a brief human-readable summary of tool call parameters for progress display."""
    if not params:
        return ""
    items = []
    for k, v in list(params.items())[:3]:
        if isinstance(v, str) and len(v) > 20:
            v = v[:17] + "..."
        items.append(f"{k}={v!r}")
    suffix = ", ..." if len(params) > 3 else ""
    return ", ".join(items) + suffix


MAX_RETRIES = 3


def get_response(
    user_message: str,
    conversation_history: list[dict],
    model: str = DEFAULT_MODEL,
    session_tracker: Optional[SessionTracker] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[str, ResponseUsage]:
    """Send a user message through the full tool-use conversation loop.

    Returns:
    - The final text response from Claude
    - A ResponseUsage object with token usage for this question

    The conversation loop:
    1. Send message + history + tools to Claude
    2. If Claude requests tool calls: execute them, append results, repeat
    3. Once Claude returns a text response: return it

    Token usage is accumulated across all API calls for this one user question.

    Args:
        progress_callback: Optional function that receives status strings for UI display.
    """
    client = anthropic.Anthropic()

    def update_progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Decide whether to include the knowledge base
    include_kb = needs_knowledge_base(user_message)
    if include_kb:
        update_progress("Loading fundraising knowledge base...")
    system_prompt = build_system_prompt(include_knowledge=include_kb)

    update_progress("Analyzing your question...")

    # Build the messages list for this turn.
    messages = conversation_history + [{"role": "user", "content": user_message}]

    # Track usage for this response (may span multiple API calls)
    response_usage = ResponseUsage(question=user_message)

    tool_call_count = 0

    while tool_call_count <= MAX_TOOL_CALLS_PER_TURN:
        # Time the API call (with retry for rate limits)
        start_time = time.time()
        response = None

        for attempt in range(MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
                break  # success
            except anthropic.RateLimitError as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt * 5  # 5s, 10s, 20s
                    update_progress(
                        f"Rate limited; waiting {wait_time}s before retry "
                        f"({attempt + 1}/{MAX_RETRIES})..."
                    )
                    time.sleep(wait_time)
                else:
                    raise  # re-raise after final attempt

        latency_ms = (time.time() - start_time) * 1000

        # Record this API call
        had_tool_use = any(block.type == "tool_use" for block in response.content)
        api_call = APICall(
            timestamp=datetime.now(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model,
            had_tool_use=had_tool_use,
            latency_ms=latency_ms,
        )
        response_usage.calls.append(api_call)

        # If Claude is done (no tool use), return the text response
        if response.stop_reason == "end_turn" or not had_tool_use:
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            final_text = "\n".join(text_blocks) if text_blocks else "(No response generated)"

            if session_tracker is not None:
                session_tracker.responses.append(response_usage)

            return final_text, response_usage

        # Claude wants to call tools; execute them and collect results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_call_count += 1
                params_summary = _summarize_tool_params(block.name, block.input)
                update_progress(f"Querying: {block.name}({params_summary})")
                result_str = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

        update_progress("Interpreting results...")

        # Append Claude's response (with tool_use blocks) and the tool results.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Safety valve: exceeded MAX_TOOL_CALLS_PER_TURN
    if session_tracker is not None:
        session_tracker.responses.append(response_usage)
    return (
        "I reached the maximum number of tool calls for this question. "
        "Please try a more specific query.",
        response_usage,
    )
```

Make sure the existing import of `from prompts import build_system_prompt` is updated to also import `needs_knowledge_base`. Remove any separate `from time import sleep` since `time.sleep` is already available through the `import time` at the top.

---

## Patch 3: progress display in app.py

### Changes to `src/app.py`

Replace the input handling block (the section starting with `if user_input:`) with the version below. The key change is replacing `st.spinner` with `st.status` and passing a `progress_callback`:

```python
if user_input:
    # Immediately display the user's message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input, "usage": None})

    # Build the conversation history to pass to the API.
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    # Call Claude with progress display
    with st.chat_message("assistant"):
        with st.status("Working on your question...", expanded=True) as status:
            try:
                response_text, response_usage = get_response(
                    user_message=user_input,
                    conversation_history=history,
                    model=st.session_state.selected_model,
                    session_tracker=st.session_state.tracker,
                    progress_callback=lambda msg: status.update(label=msg),
                )
                status.update(label="Done", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Error", state="error", expanded=False)
                response_text = (
                    f"**Error:** {e}\n\n"
                    "Please check your ANTHROPIC_API_KEY in `.env` and try again."
                )
                response_usage = None

        st.markdown(response_text)
        if response_usage is not None:
            st.caption(response_usage.format_inline(st.session_state.selected_model))

    # Persist the assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "usage": response_usage,
    })
```

---

## Patch 4: prompt caching for system prompt and tools

### Background

The Anthropic API supports prompt caching, which caches the processed prefix of a request (system prompt + tools + early messages) for 5 minutes. On cache hits, cached input tokens are charged at 10% of the normal rate and latency drops significantly. Cache writes cost 25% more than normal input. For our use case (same system prompt and tools on every call, multiple calls per minute), the savings are substantial.

The current API (no beta header required for newer models) supports `cache_control` fields on system prompt blocks and tool definitions. The system caches everything up to and including the block marked with `cache_control`.

### How it works

Cache prefixes are built in this order: **tools → system → messages**. We want to cache the tools and system prompt since these are identical across calls. To do this, add `cache_control` to:

1. The last tool definition (caches all 7 tools).
2. The last system prompt block (caches the entire system prompt; or, if the KB is included, put the breakpoint on the KB block so the base prompt is always cached).

### Changes to `src/llm.py`

**Restructure the system prompt as a list of blocks** instead of a single string, so we can place `cache_control` on specific blocks.

First, change `build_system_prompt()` in `src/prompts.py` to return a list:

```python
def build_system_prompt(include_knowledge: bool = False) -> list[dict]:
    """Assemble the system prompt as a list of content blocks for the API.

    Returns a list of dicts suitable for the 'system' parameter of messages.create().
    The last block gets cache_control so the entire system prompt is cached.
    """
    # Base prompt + schema is always present
    base_content = BASE_SYSTEM_PROMPT + DB_SCHEMA_SUMMARY

    if include_knowledge:
        kb_content = load_knowledge_base()
        # Two blocks: base (cacheable on its own) + KB (with cache breakpoint)
        return [
            {"type": "text", "text": base_content},
            {
                "type": "text",
                "text": kb_content,
                "cache_control": {"type": "ephemeral"},
            },
        ]
    else:
        fallback_note = (
            "\n\nNote: A fundraising best-practices knowledge base is available. "
            "If the user asks about strategy, best practices, or 'how to' questions "
            "about fundraising, let them know you can provide guidance and ask them "
            "to rephrase if needed.\n"
        )
        return [
            {
                "type": "text",
                "text": base_content + fallback_note,
                "cache_control": {"type": "ephemeral"},
            },
        ]
```

**Add `cache_control` to the last tool definition** in the `TOOLS` list in `src/llm.py`. Find the last tool (`plan_fundraising_trip`) and add `cache_control` to it:

```python
    {
        "name": "plan_fundraising_trip",
        "description": "Find the best contacts to meet during a fundraising trip ...",
        "cache_control": {"type": "ephemeral"},  # <-- ADD THIS LINE
        "input_schema": {
            # ... (keep existing schema unchanged)
        }
    },
```

Only add it to the LAST tool; the cache is cumulative so it covers all preceding tools.

**Update the token tracker** to report cache hits. In `src/token_tracker.py`, update the `APICall` dataclass:

```python
@dataclass
class APICall:
    """A single API call within a response."""
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    model: str
    had_tool_use: bool
    latency_ms: float
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
```

In `ResponseUsage`, add properties:

```python
    @property
    def total_cache_read_tokens(self) -> int:
        return sum(c.cache_read_input_tokens for c in self.calls)

    @property
    def total_cache_creation_tokens(self) -> int:
        return sum(c.cache_creation_input_tokens for c in self.calls)
```

Update `format_inline` to show cache hits:

```python
    def format_inline(self, model: str) -> str:
        """Format for display below a chat response."""
        cost = self.estimated_cost(model)
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
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
```

Update the `estimated_cost` method to account for caching pricing (reads at 10%, writes at 125%):

```python
    def estimated_cost(self, model: str) -> float:
        """Estimated cost in dollars, accounting for prompt caching."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
        base_rate = pricing["input_per_mtok"]

        total_cost = 0.0
        for call in self.calls:
            # Non-cached input tokens at base rate
            regular_input = call.input_tokens - call.cache_creation_input_tokens - call.cache_read_input_tokens
            total_cost += (regular_input / 1_000_000) * base_rate
            # Cache writes at 1.25x
            total_cost += (call.cache_creation_input_tokens / 1_000_000) * base_rate * 1.25
            # Cache reads at 0.1x
            total_cost += (call.cache_read_input_tokens / 1_000_000) * base_rate * 0.1
            # Output tokens
            total_cost += (call.output_tokens / 1_000_000) * pricing["output_per_mtok"]

        return total_cost
```

**Capture cache fields from the API response** in the `get_response()` loop in `src/llm.py`. Where the `APICall` is constructed, update it:

```python
        api_call = APICall(
            timestamp=datetime.now(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model,
            had_tool_use=had_tool_use,
            latency_ms=latency_ms,
            cache_creation_input_tokens=getattr(response.usage, 'cache_creation_input_tokens', 0) or 0,
            cache_read_input_tokens=getattr(response.usage, 'cache_read_input_tokens', 0) or 0,
        )
```

We use `getattr` with a fallback because these fields only appear when caching is active.

### Important notes on prompt caching

- **Minimum cacheable prefix**: 1,024 tokens for Sonnet, 2,048 for Haiku. Our system prompt + tools exceed this, so caching will always be eligible.
- **Cache TTL**: 5 minutes by default; refreshed on each hit. Since our users ask multiple questions per session, the cache will stay warm.
- **No beta header needed**: For Claude Sonnet 4 and Claude Haiku 4.5, prompt caching is GA. The old `anthropic-beta: prompt-caching-2024-07-31` header is only needed for deprecated models (Claude 3.0 Haiku, Claude 3.5 Sonnet v1). Our models do not require it.
- **Cache key stability**: The cache key is a hash of all content up to the `cache_control` breakpoint. Our tools and base system prompt are static, so they will cache reliably. The only thing that changes is whether the KB block is appended.

---

## Patch 5: compact the knowledge base

### Instructions

The file `knowledge/fundraising_best_practices.md` is currently 13,740 bytes (~2,500 words, ~5,000 tokens when combined with `iasc_context.md`). This is larger than the 1,500-2,000 word target from the original spec.

Compact it to **1,000-1,200 words** while preserving all of the following sections and their key data points:

1. **Donor lifecycle stages** (prospect → first-time → repeat → major → lapsed); keep the stage names and one-sentence definitions
2. **RFM analysis** (recency, frequency, monetary); keep the framework name and how to apply it to small nonprofits
3. **Lapsed donor re-engagement**; keep the 5-15% reactivation benchmark, the recommended window (6-24 months), and 2-3 tactical tips
4. **Major gift fundraising**; keep the donor pyramid concept, qualification criteria (capacity, affinity, propensity), and the "center-out" approach reference
5. **Prospect research and wealth screening**; keep what wealth scores indicate and their limitations
6. **Email and digital engagement benchmarks**; keep the open rate (15-25%) and click rate (2-5%) benchmarks and the correlation with giving
7. **Key metrics**; keep retention rate, lifetime value, average gift growth, cost per dollar raised

Rules for compaction:
- Use terse, reference-card style (not narrative prose)
- Prefer tables and short bullet points over paragraphs
- Remove all introductory/transitional sentences
- Remove examples that restate the same point in different words
- Do NOT add new information; only compress what is already there
- Keep the XML-friendly markdown format (no HTML tags)

After compacting, verify the word count is between 1,000 and 1,200 words:

```bash
wc -w knowledge/fundraising_best_practices.md
```

Also verify the overall knowledge base token estimate dropped. You can check with:

```python
python3 -c "
import sys; sys.path.insert(0, 'src')
from knowledge import get_knowledge_token_estimate
print(f'Estimated KB tokens: {get_knowledge_token_estimate():,}')
"
```

Target: under 1,500 tokens total for both KB files combined (down from ~3,500).

Do NOT change `knowledge/iasc_context.md`; it is already appropriately sized (~800 words).

---

## Verification checklist

After applying all patches:

1. `pytest tests/test_queries.py` passes (data layer unchanged)
2. Run the app (`streamlit run src/app.py`) and test:
   - **Simple data query**: "How many donors in NYC?" should work WITHOUT loading the KB (check that the status shows "Analyzing your question..." then "Querying: search_donors(...)" but NOT "Loading fundraising knowledge base...")
   - **KB query**: "What are best practices for re-engaging lapsed donors?" SHOULD load the KB (status shows "Loading fundraising knowledge base...")
   - **Rate limit resilience**: Ask two questions in quick succession; the second should show "Rate limited; waiting 5s..." and then succeed, not crash
   - **Cache hits**: On the second question within 5 minutes, token usage should show cached tokens in the inline stats
   - **Progress display**: The status widget should update at each step, not just show a static spinner
3. Check the sidebar "Session usage" still accumulates correctly across questions
4. Check `knowledge/fundraising_best_practices.md` is between 1,000-1,200 words

---

## Summary of expected token savings

| Scenario | Before (per API call) | After (per API call) |
|---|---|---|
| Data query, no cache | ~8,300 input tokens | ~3,300 input tokens |
| Data query, cache hit | ~8,300 input tokens | ~3,300 total, ~2,800 cached (charged at 10%) |
| KB query, no cache | ~8,300 input tokens | ~5,500 input tokens (KB is smaller now) |
| KB query, cache hit | ~8,300 input tokens | ~5,500 total, ~5,000 cached |

Combined effect for a typical two-tool-call data query within a session:
- Before: ~25,000 input tokens billed at full rate
- After: ~10,000 input tokens, most cached at 10% rate
- Effective cost reduction: ~80-85%

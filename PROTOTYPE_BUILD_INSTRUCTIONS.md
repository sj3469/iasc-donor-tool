# Build instructions: IASC donor analytics prototype

These instructions are for Claude Code to build a working prototype of the AI-powered donor analytics tool. Read CLAUDE.md first for full project context.

## Goal

Build a functional Streamlit application where a user can type natural language questions about a donor database and receive data-grounded answers powered by Claude. The prototype should be good enough to demo to IASC stakeholders (Andrew and Rosemary) and to serve as a reference implementation for 28 graduate students building the production version.

## Parallel build strategy

This project has four independent workstreams. Use subagents (via the Task tool) to build A, B, and C in parallel, then integrate in D.

```
  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
  │  Workstream A       │   │  Workstream B       │   │  Workstream C       │
  │  DATA LAYER         │   │  KNOWLEDGE BASE     │   │  QUERY FUNCTIONS    │
  │                     │   │                     │   │                     │
  │  Step 1: mock data  │   │  Step 2a: KB docs   │   │  Step 3: queries.py │
  │  Step 2: data dict  │   │  Step 2b: loader    │   │  Step 6a: unit tests│
  │                     │   │                     │   │                     │
  └────────┬────────────┘   └────────┬────────────┘   └────────┬────────────┘
           │                         │                          │
           └─────────────────────────┼──────────────────────────┘
                                     │
                              ┌──────▼──────────────┐
                              │  Workstream D       │
                              │  LLM + UI + INTEG.  │
                              │                     │
                              │  Step 4: llm.py     │
                              │  Step 4a: tracker   │
                              │  Step 5: app.py     │
                              │  Step 6b: scenarios  │
                              │  Step 7: README     │
                              │  Step 8: build log  │
                              └─────────────────────┘
```

**Workstream A** (data layer): Steps 1 and 2. No dependencies.
**Workstream B** (knowledge base): Steps 2a and 2b. No dependencies.
**Workstream C** (query functions): Step 3 and unit tests. Depends on Step 1 schema only (not data generation; can use a small hardcoded test fixture).
**Workstream D** (LLM, token tracking, UI, integration): Steps 4, 4a, 5, 6b, 7, 8. Depends on A, B, and C.

Launch workstreams A, B, and C as parallel subagents. Once all three complete, proceed with D sequentially.

## Prerequisites

- Python 3.11+
- An Anthropic API key (set as ANTHROPIC_API_KEY environment variable)
- No other external services required; everything runs locally

## Step 0: Project setup

Create the project directory structure as specified in CLAUDE.md. Initialize with:

```
iasc-donor-tool/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── data/
├── src/
├── tests/
└── docs/
```

requirements.txt should contain:
```
streamlit>=1.30.0
anthropic>=0.40.0
pandas>=2.0.0
plotly>=5.18.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

.env.example:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## Step 1: Generate the mock donor database

Create `data/generate_mock_data.py` that produces a SQLite database (`data/donors.db`) with 300 synthetic donor records. This is the most important step; the quality of the mock data determines how realistic the demo feels.

### Table: contacts

This is the main donor/prospect table. 300 rows.

| Column | Type | Description | Realistic values |
|--------|------|-------------|-----------------|
| contact_id | TEXT PK | Salesforce-style ID | Format: 003XX00000XXXXXX (18 chars) |
| first_name | TEXT | Fake first name | Use faker or a list of 100+ names |
| last_name | TEXT | Fake last name | Use faker or a list of 100+ names |
| email | TEXT | Fake email | firstname.lastname@example.com |
| city | TEXT | City name | Cluster around: Charlottesville VA, NYC, DC, Boston, Chicago, SF, Houston, plus scattered |
| state | TEXT | 2-letter state code | VA should be ~20% of records (IASC home base) |
| zip_code | TEXT | Mailing zip | Use real zip prefixes: 229xx (Charlottesville), 100xx (NYC), 200xx (DC), 021xx (Boston) |
| donor_status | TEXT | Current status | Values: "active", "lapsed", "prospect", "new_donor". Distribution: ~35% active, ~25% lapsed, ~25% prospect, ~15% new_donor |
| contact_created_date | DATE | When record was created in Salesforce | Range: 1993-2025, most between 2005-2020 |
| first_gift_date | DATE or NULL | Date of first gift | NULL for prospects who never gave. Use real sample range: 1993-2025 |
| last_gift_date | DATE or NULL | Date of most recent gift | NULL for prospects. For lapsed: at least 2 years before today |
| total_gifts | REAL or NULL | Lifetime giving total | Use power-law distribution inspired by real sample: most give $50-$500 total; a few give $10K-$100K; rare outliers at $500K-$8M |
| total_number_of_gifts | INT or NULL | Count of gifts | Range 0-60+. Correlated with total_gifts but not perfectly |
| average_gift | REAL or NULL | Average gift amount | = total_gifts / total_number_of_gifts |
| giving_vehicle | TEXT or NULL | How they give | Values: "check", "online", "stock", "DAF" (donor-advised fund), "wire". Most common: "online" and "check" |
| subscription_type | TEXT | Hedgehog Review subscription | Values: "print", "digital", "both", "none". About 60% should have some subscription |
| subscription_status | TEXT | Current subscription state | Values: "active", "expired", "never". Correlate with donor_status |
| subscription_start_date | DATE or NULL | When subscription began | NULL if subscription_type is "none" |
| email_open_rate | REAL or NULL | MailChimp open rate | Range 0.0-0.9. Average around 0.25. NULL for ~15% of records (no email on file) |
| last_email_click_date | DATE or NULL | Last click in a MailChimp email | NULL for many; within last 2 years for engaged contacts |
| event_attendance_count | INT | Number of IASC events attended | Range 0-12. Most are 0; a few are 3-8 |
| wealth_score | INT or NULL | WealthEngine wealth rating | Range 1-10 (10 = highest capacity). NULL for ~40% of records (no WealthEngine match). Loosely correlated with total_gifts |
| notes | TEXT or NULL | Free-text notes | Short strings like "Met at UVA event 2019", "Board member referral", "Prefers email contact". About 30% of records have notes. |

### Important data generation rules

1. **Consistency**: If donor_status is "prospect", then first_gift_date, last_gift_date, total_gifts, total_number_of_gifts, average_gift, and giving_vehicle should all be NULL. Prospects are people who subscribe or attend events but haven't donated yet.

2. **Lapsed logic**: If donor_status is "lapsed", last_gift_date should be at least 2 years ago (before 2024-02-25). They may still have active subscriptions.

3. **Geographic clustering**: About 20% of contacts should be in Virginia (especially Charlottesville 229xx area). About 15% in the NYC metro area (100xx, 070xx, 068xx). About 10% in DC metro (200xx, 201xx, 220xx, 221xx). The rest scattered nationally.

4. **Gift distribution**: Follow a power law. Use the real sample as guidance:
   - ~40% of donors gave $10-$500 total
   - ~25% gave $500-$5,000
   - ~15% gave $5,000-$50,000
   - ~10% gave $50,000-$500,000
   - ~5% gave $500,000+
   - A few outliers at $1M-$8M (these exist in the real data)

5. **Engagement correlation**: Higher wealth_score and higher email_open_rate should loosely (but not perfectly) correlate with higher total_gifts. Some high-wealth prospects have never given; some low-wealth donors are very loyal.

6. **Temporal realism**: first_gift_date should always be before last_gift_date. contact_created_date should be on or before first_gift_date. Use realistic date ranges; no gifts before 1990 or after today.

7. **Names**: Use realistic but clearly fake American names. Include some diversity in name origins. Do NOT use names of real people.

### Table: gifts

Individual gift transactions. Generate 1-60+ rows per donor (matching total_number_of_gifts from the contacts table). Prospects have no gift records.

| Column | Type | Description |
|--------|------|-------------|
| gift_id | INT PK | Auto-increment |
| contact_id | TEXT FK | References contacts.contact_id |
| gift_date | DATE | Date of this gift |
| amount | REAL | Gift amount in dollars |
| gift_type | TEXT | "one_time", "recurring", "planned_giving", "event" |
| campaign | TEXT or NULL | e.g., "Annual Fund 2023", "Year-End Appeal 2024", "Hedgehog Gala 2022" |

Gift dates should be distributed between the contact's first_gift_date and last_gift_date. Individual amounts should roughly average to the contact's average_gift (with some variance). Most gifts should be one_time or recurring.

### Table: interactions

Engagement history beyond gifts. Optional but useful for demo queries.

| Column | Type | Description |
|--------|------|-------------|
| interaction_id | INT PK | Auto-increment |
| contact_id | TEXT FK | References contacts.contact_id |
| interaction_date | DATE | When it happened |
| interaction_type | TEXT | "email_open", "email_click", "event_attended", "meeting", "phone_call", "mail_sent" |
| details | TEXT or NULL | Brief note |

Generate 0-20 interactions per contact. More engaged contacts (higher email_open_rate, more event_attendance) should have more interactions.

### After generation

Print summary statistics:
- Total contacts by donor_status
- Total contacts by state (top 10)
- Gift amount distribution (min, median, mean, max, total)
- Subscription breakdown
- Wealth score coverage

---

## Step 2: Create the data dictionary

Create `data/data_dictionary.md` documenting every field in the database. For each field, include:
- Field name
- Data type
- Source system (Salesforce, MailChimp, WealthEngine, or Derived)
- Description (one sentence)
- Example values
- Handling of NULLs

This is important documentation that students will reference.

---

## Step 2a: Create the fundraising knowledge base

Create two markdown files in the `knowledge/` directory. These are injected into the system prompt so Claude can reference fundraising best practices when answering questions. This is designed to be replaceable later with RAG or a Claude Skill.

### knowledge/fundraising_best_practices.md

Write a concise reference document (roughly 1500-2000 words) covering the following topics. Use clear section headers. This document should read like a practitioner's cheat sheet, not an academic paper.

**Donor lifecycle and segmentation:**
- The standard donor pipeline stages: prospect, first-time donor, repeat donor, major donor, lapsed donor
- RFM analysis (recency, frequency, monetary value) and how to adapt it for small nonprofits where most donors give once per year
- The difference between donor retention and donor acquisition; why retention is cheaper
- Moves management: the concept of systematically advancing donors through cultivation stages

**Lapsed donor re-engagement:**
- Industry benchmarks: typical lapsed donor re-activation rates (5-15%)
- Signals that a lapsed donor may be ready to re-engage (renewed subscription, event attendance, email opens)
- Best practices for re-engagement outreach (personalized messaging, acknowledging gap, soft ask vs. direct ask)

**Major gift fundraising:**
- The donor pyramid concept: many small donors at the base, few major donors at the top
- Qualification criteria for major gift prospects: capacity (can they give?), affinity (do they care?), propensity (will they give?)
- The importance of personal meetings; why major gifts require face-to-face cultivation
- Trip planning best practices: how to prioritize which donors to visit; the "center-out" approach (start with closest relationships, expand outward)

**Prospect research and wealth screening:**
- What wealth indicators mean: real estate, stock holdings, business ownership, philanthropic history
- Limitations of wealth screening: capacity does not equal willingness; false positives are common
- Ethical considerations: respect for privacy, avoiding assumptions based on demographics

**Email and digital engagement:**
- Typical nonprofit email open rates (15-25%) and click rates (2-5%)
- How to interpret engagement signals: opens suggest awareness, clicks suggest interest, sustained engagement suggests affinity
- The relationship between digital engagement and giving: engaged subscribers are 3-5x more likely to donate

**Metrics that matter:**
- Donor retention rate (percentage of donors who give again the following year)
- Donor lifetime value (total expected giving over the relationship)
- Average gift size and how it typically grows over time for retained donors
- Cost per dollar raised (benchmarks for different fundraising channels)

**Important:** Do not cite specific publications or statistics you are not confident about. Use ranges and qualitative guidance (e.g., "industry benchmarks suggest..." or "many small nonprofits find that..."). If referencing well-known frameworks (RFM, donor pyramid, moves management), name them but don't fabricate citation details.

### knowledge/iasc_context.md

Write a short document (roughly 500-800 words) summarizing what we know about IASC's specific situation, drawn from the project files:

- IASC is a research center and nonprofit publisher at the University of Virginia
- They publish The Hedgehog Review, a journal of critical reflections on contemporary culture
- Development team is 2 people: Andrew Westhouse (CDO, strategy-focused, does fundraising trips) and Rosemary Armato (Development Coordinator, manages data and operations)
- Data lives in Salesforce (donor records), MailChimp (email campaigns), and WealthEngine (wealth screening)
- Rosemary currently exports data manually from Salesforce into spreadsheets for analysis
- Andrew uses a "center-out" fundraising approach: start with closest supporters and expand outward
- They are in a cultivation phase, focused on acquiring new donors and re-engaging lapsed ones
- Donor base is small (hundreds, not thousands); most donors give once per year around year-end
- They raised $15,000 in a recent campaign; focus was on new donor acquisition, not dollar amounts
- They have fragmented data across systems and many records with incomplete information
- Geographic concentration: Charlottesville/Virginia area plus supporters in Northeast corridor and other metro areas
- WealthEngine matching is expensive and doesn't always return results

### knowledge/README.md

Brief file (10-15 lines) explaining:
- What these files are and how they are used (injected into the system prompt)
- How to add new content (just edit the markdown files; the loader will pick up changes)
- Future directions: this could become a RAG pipeline over a larger document collection, or a Claude Skill with its own tools

---

## Step 2b: Build the knowledge base loader

Create `src/knowledge.py` that loads and formats the knowledge base files for injection into the system prompt.

```python
"""
Knowledge base loader for fundraising best practices and IASC context.

Currently: reads markdown files and injects them into the system prompt.
Future: could be replaced with RAG retrieval, a Claude Skill, or MCP tool.
"""

import os
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

def load_knowledge_base() -> str:
    """Load all knowledge base documents and format them for the system prompt.
    
    Returns a formatted string with XML-style tags wrapping each document,
    so Claude can distinguish between different knowledge sources.
    """
    sections = []
    
    # Load fundraising best practices
    practices_path = KNOWLEDGE_DIR / "fundraising_best_practices.md"
    if practices_path.exists():
        content = practices_path.read_text(encoding="utf-8")
        sections.append(
            f"<fundraising_knowledge>\n{content}\n</fundraising_knowledge>"
        )
    
    # Load IASC-specific context
    context_path = KNOWLEDGE_DIR / "iasc_context.md"
    if context_path.exists():
        content = context_path.read_text(encoding="utf-8")
        sections.append(
            f"<iasc_context>\n{content}\n</iasc_context>"
        )
    
    if not sections:
        return ""
    
    return (
        "\n\n## Reference knowledge\n\n"
        "The following reference materials are available to inform your responses. "
        "Use them when relevant, but always prioritize actual data from the donor database "
        "over general best practices.\n\n"
        + "\n\n".join(sections)
    )


def get_knowledge_token_estimate() -> int:
    """Rough estimate of tokens used by the knowledge base.
    Useful for budget planning. Assumes ~0.75 tokens per word.
    """
    total_words = 0
    for filename in ["fundraising_best_practices.md", "iasc_context.md"]:
        filepath = KNOWLEDGE_DIR / filename
        if filepath.exists():
            total_words += len(filepath.read_text(encoding="utf-8").split())
    return int(total_words * 0.75)
```

The key design decision here: we use XML-style tags (`<fundraising_knowledge>`, `<iasc_context>`) to wrap each document. This makes it easy for Claude to distinguish between general best practices and IASC-specific context, and it sets up a clean migration path to RAG later (where you'd retrieve relevant chunks and wrap them the same way).

---

## Step 3: Build the query functions (tools for Claude)

Create `src/queries.py` with Python functions that Claude can call via tool use. These are the "skills" that ground Claude's responses in actual data.

Each function should:
- Accept clear, typed parameters
- Return a pandas DataFrame or a summary dict
- Handle edge cases (no results, invalid filters) gracefully
- Include a docstring that describes what it does (Claude will see these)

### Required query functions

```python
def search_donors(
    state: str | None = None,
    city: str | None = None,
    zip_prefix: str | None = None,
    donor_status: str | None = None,
    min_total_gifts: float | None = None,
    max_total_gifts: float | None = None,
    min_gift_count: int | None = None,
    subscription_type: str | None = None,
    subscription_status: str | None = None,
    min_wealth_score: int | None = None,
    last_gift_before: str | None = None,
    last_gift_after: str | None = None,
    min_email_open_rate: float | None = None,
    has_attended_events: bool | None = None,
    sort_by: str = "total_gifts",
    sort_order: str = "desc",
    limit: int = 20
) -> dict:
    """Search and filter the donor database. Returns matching contacts with key fields.
    Use this for any question about finding, filtering, or listing donors."""

def get_donor_detail(contact_id: str) -> dict:
    """Get complete information about a single donor including gift history
    and interactions. Use when the user asks about a specific person."""

def get_summary_statistics(
    group_by: str | None = None,
    filter_status: str | None = None,
    filter_state: str | None = None
) -> dict:
    """Get aggregate statistics about the donor base. Use for questions about
    totals, averages, distributions, and comparisons across segments."""

def get_geographic_distribution(
    min_total_gifts: float | None = None,
    donor_status: str | None = None,
    top_n: int = 15
) -> dict:
    """Get donor counts and total giving by state or city.
    Use for geographic analysis and trip planning questions."""

def get_lapsed_donors(
    months_since_last_gift: int = 24,
    min_previous_total: float | None = None,
    state: str | None = None,
    limit: int = 20
) -> dict:
    """Find donors who haven't given recently but have a giving history.
    Use for re-engagement and lapsed donor questions."""

def get_prospects_by_potential(
    has_subscription: bool | None = None,
    min_wealth_score: int | None = None,
    min_email_open_rate: float | None = None,
    has_attended_events: bool | None = None,
    state: str | None = None,
    limit: int = 20
) -> dict:
    """Find prospects (non-donors) ranked by engagement signals and wealth indicators.
    Use for prospecting and lead generation questions."""

def plan_fundraising_trip(
    target_city: str | None = None,
    target_state: str | None = None,
    target_zip_prefix: str | None = None,
    min_total_gifts: float | None = None,
    include_prospects: bool = True,
    include_lapsed: bool = True,
    limit: int = 10
) -> dict:
    """Find the best contacts to meet during a fundraising trip to a specific area.
    Ranks by a combination of giving history, engagement, wealth score, and recency.
    Use for trip planning and meeting prioritization questions."""
```

Each function should query the SQLite database and return a dict with:
- `results`: list of dicts (the actual data rows)
- `count`: total matching records
- `summary`: a brief text description of the result set

### Scoring logic for trip planning

The `plan_fundraising_trip` function should compute a composite score for ranking. A simple weighted formula:

```
score = (
    0.3 * normalized_total_gifts +
    0.2 * normalized_wealth_score +
    0.2 * recency_score +           # higher if more recent gift or engagement
    0.15 * engagement_score +        # email opens + event attendance
    0.15 * subscription_score        # active subscriber gets a boost
)
```

Normalize each component to 0-1 range. This doesn't need to be perfect; it needs to be explainable.

---

## Step 4: Build the LLM integration

Create `src/llm.py` with the Claude API integration using tool use (function calling).

### System prompt (in src/prompts.py)

The system prompt is assembled dynamically from a base prompt plus the knowledge base content.

```python
from knowledge import load_knowledge_base

BASE_SYSTEM_PROMPT = """You are a donor analytics assistant for the Institute for Advanced Studies in Culture (IASC), a nonprofit research center and publisher at the University of Virginia. IASC publishes The Hedgehog Review, a journal of critical reflections on contemporary culture.

You help IASC's development team (primarily Andrew Westhouse, Chief Development Officer, and Rosemary Armato, Development Coordinator) analyze their donor data and make informed decisions about fundraising outreach.

When answering questions:
1. Always use the provided tools to query actual data. Never make up donor names, amounts, or other facts.
2. Explain your reasoning: what filters you applied, how you ranked results, and any assumptions you made.
3. When presenting lists of donors, include key details: name, location, total giving, last gift date, and any relevant engagement indicators.
4. If a query returns no results, say so clearly and suggest how to broaden the search.
5. When recommending donors for meetings or outreach, briefly explain why each person is a good candidate.
6. Be concise but thorough. Development officers need actionable information, not lengthy narratives.
7. When relevant, reference fundraising best practices from your knowledge base to contextualize your recommendations (e.g., mention lapsed donor re-engagement benchmarks, or explain why you're weighting certain factors in a trip plan).
8. Use dollar formatting for amounts ($1,234.56) and standard date formats.
9. If asked about fundraising strategy or best practices, draw on the reference knowledge provided below, but note that specific strategic decisions should involve Andrew and Rosemary's institutional knowledge.

Context about IASC's fundraising:
- IASC is a small nonprofit; their donor base is in the hundreds, not thousands.
- Most donors give once per year, often in response to year-end appeals.
- Andrew uses a "center-out" approach: starting with the closest supporters and expanding outward.
- They are in a cultivation phase, focused on acquiring new donors and re-engaging lapsed ones.
- The Hedgehog Review subscriber list is a key source of prospects.
- IASC is based in Charlottesville, Virginia, but has supporters nationwide.
- They track donors in Salesforce, email engagement in MailChimp, and wealth data via WealthEngine.
"""

def build_system_prompt() -> str:
    """Assemble the full system prompt: base instructions + knowledge base."""
    kb_content = load_knowledge_base()
    return BASE_SYSTEM_PROMPT + kb_content
```

The knowledge base adds roughly 1500-2500 tokens to each API call. This is a deliberate tradeoff: it costs a fraction of a cent per query but gives Claude significantly better context for fundraising-related recommendations. Track this cost via the token tracker (Step 4a).

### Tool definitions

Convert each query function from Step 3 into a Claude tool definition. The tool names and descriptions should match the function docstrings. Parameter descriptions should be clear enough that Claude can decide which parameters to use based on the user's question.

### Conversation flow

The LLM integration should handle a multi-turn conversation:

1. User asks a question
2. Send the question + conversation history + tools + system prompt (with knowledge base) to Claude
3. If Claude wants to call a tool: execute the function, return results to Claude
4. Claude may call multiple tools in sequence (e.g., first search_donors, then get_donor_detail)
5. Once Claude has enough data, it generates the final response
6. Capture token usage from the API response and pass it to the token tracker
7. Display the response with inline token usage metadata

Track token usage (input + output) for each API call and log it. See Step 4a.

---

## Step 4a: Build the token usage tracker

Create `src/token_tracker.py` to track and display API usage per response and per session.

The Anthropic API returns token usage in every response object via `response.usage.input_tokens` and `response.usage.output_tokens`. For tool-use conversations, there may be multiple API calls per user question (the initial call, plus one per tool result round-trip). The tracker must accumulate across all calls within a single user question.

```python
"""
Token usage tracker for the IASC donor analytics tool.

Tracks per-response and per-session token usage and estimated costs.
Designed to be displayed inline with each response and in the Streamlit sidebar.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime


# Pricing as of early 2025; update these if pricing changes.
# Source: anthropic.com/pricing
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {
        "input_per_mtok": 3.00,    # $ per million input tokens
        "output_per_mtok": 15.00,  # $ per million output tokens
        "display_name": "Sonnet",
    },
    "claude-haiku-4-5-20251001": {
        "input_per_mtok": 0.80,
        "output_per_mtok": 4.00,
        "display_name": "Haiku",
    },
}


@dataclass
class APICall:
    """A single API call within a response."""
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    model: str
    had_tool_use: bool
    latency_ms: float


@dataclass
class ResponseUsage:
    """Aggregated usage for one user question (may involve multiple API calls)."""
    question: str
    calls: list[APICall] = field(default_factory=list)
    
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
    
    def estimated_cost(self, model: str) -> float:
        """Estimated cost in dollars."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input_per_mtok"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output_per_mtok"]
        return input_cost + output_cost

    def format_inline(self, model: str) -> str:
        """Format for display below a chat response."""
        cost = self.estimated_cost(model)
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
        model_name = pricing["display_name"]
        return (
            f"📊 {model_name} · {self.num_api_calls} API call(s) · "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens · "
            f"${cost:.4f} · {self.total_latency_ms:.0f}ms"
        )


class SessionTracker:
    """Tracks all API usage within a Streamlit session."""
    
    def __init__(self):
        self.responses: list[ResponseUsage] = []
    
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
        model = self.responses[-1].calls[-1].model if self.responses[-1].calls else "claude-sonnet-4-20250514"
        return sum(r.estimated_cost(model) for r in self.responses)
    
    @property
    def total_api_calls(self) -> int:
        return sum(r.num_api_calls for r in self.responses)
    
    def format_sidebar(self) -> str:
        """Format summary for the Streamlit sidebar."""
        return (
            f"**Session usage**\n\n"
            f"- Questions asked: {len(self.responses)}\n"
            f"- API calls: {self.total_api_calls}\n"
            f"- Input tokens: {self.total_input_tokens:,}\n"
            f"- Output tokens: {self.total_output_tokens:,}\n"
            f"- Estimated cost: ${self.total_cost:.4f}\n"
        )
```

### Integration with llm.py

In the LLM conversation loop, wrap each `client.messages.create()` call with timing:

```python
start_time = time.time()
response = client.messages.create(...)
latency_ms = (time.time() - start_time) * 1000

api_call = APICall(
    timestamp=datetime.now(),
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    model=model_name,
    had_tool_use=any(block.type == "tool_use" for block in response.content),
    latency_ms=latency_ms,
)
current_response_usage.calls.append(api_call)
```

### Integration with app.py

After each assistant response in the chat, display the token usage inline using a small, muted Streamlit caption:

```python
st.caption(response_usage.format_inline(model_name))
```

In the sidebar, display the running session total:

```python
st.sidebar.markdown(tracker.format_sidebar())
```

Store the SessionTracker in `st.session_state` so it persists across Streamlit reruns.

---

## Step 5: Build the Streamlit UI

Create `src/app.py` as the main Streamlit application.

### Layout

```
┌──────────────────────────────────────────────────────┐
│  IASC Donor Analytics Assistant          [sidebar →] │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Chat history (scrollable)                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ 👤 Which donors in NYC should we visit       │   │
│  │    in April?                                  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 🤖 Based on your donor data, here are the    │   │
│  │    top 5 contacts in the NYC area...          │   │
│  │    [table of results]                         │   │
│  │                                               │   │
│  │  📊 Sonnet · 3 API calls · 2,847 in +        │   │
│  │     512 out tokens · $0.0162 · 1,230ms        │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ Ask a question about your donors...    [Send] │   │
│  └──────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────┤
│  SIDEBAR:                                            │
│  ┌────────────────────┐                              │
│  │ Quick stats        │                              │
│  │ • 300 contacts     │                              │
│  │ • 187 donors       │                              │
│  │ • $X.XM total      │                              │
│  │ • 75 prospects     │                              │
│  ├────────────────────┤                              │
│  │ Sample questions    │                              │
│  │ (clickable)        │                              │
│  ├────────────────────┤                              │
│  │ Session usage      │                              │
│  │ • Questions: 4     │                              │
│  │ • API calls: 11    │                              │
│  │ • Tokens: 12,340   │                              │
│  │ • Cost: $0.0523    │                              │
│  ├────────────────────┤                              │
│  │ Model: Sonnet ▾    │                              │
│  │ KB tokens: ~1,800  │                              │
│  └────────────────────┘                              │
└──────────────────────────────────────────────────────┘
```

### Sidebar features

1. **Quick stats**: Total contacts, donors, prospects, lapsed; total lifetime giving; average gift
2. **Sample questions** (clickable buttons that populate the chat input):
   - "Who are our top 10 donors by lifetime giving?"
   - "Which lapsed donors in Virginia should we re-engage?"
   - "Plan a fundraising trip to NYC: who should we meet?"
   - "How many subscribers have never donated but have high wealth scores?"
   - "Show me giving trends over the last 5 years"
   - "Which new donors from 2024 should we cultivate?"
   - "What are best practices for re-engaging lapsed donors?" (tests knowledge base)
3. **Session usage** (from SessionTracker): Questions asked, total API calls, total tokens, estimated cost
4. **Model selector**: Dropdown to switch between Claude Sonnet and Haiku (for cost comparison)
5. **Knowledge base info**: Display approximate token count of the loaded knowledge base (from `get_knowledge_token_estimate()`), so the user understands the per-query overhead

### Chat features

- Maintain conversation history in st.session_state
- Display data tables inline when Claude's response references specific donor lists
- Show a spinner while waiting for Claude's response
- After each assistant response, display a muted `st.caption` line showing: model name, number of API calls, input/output tokens, estimated cost, and total latency (use `ResponseUsage.format_inline()`)
- Display any errors gracefully (API errors, query errors)
- Add a "Clear conversation" button (also resets the session token tracker)

### Data display

When Claude returns a list of donors, format it as a clean Streamlit dataframe or table. Include columns: Name, City/State, Total Giving, Last Gift, Donor Status, Wealth Score. Add conditional formatting if possible (e.g., highlight high wealth scores).

---

## Step 6: Write tests

### Unit tests (tests/test_queries.py)

Test each query function with known inputs:
- search_donors with state="VA" returns only Virginia contacts
- get_lapsed_donors returns only contacts with old last_gift_date
- plan_fundraising_trip returns scored and sorted results
- Edge cases: empty results, invalid parameters

### Behavioral tests (tests/test_scenarios.py)

These are the scenarios that matter for the demo. Each test sends a natural language question through the full pipeline (LLM + tools) and checks that the response meets basic criteria.

```python
SCENARIOS = [
    {
        "query": "Who are our top 5 donors by total giving?",
        "must_contain": ["$"],  # Should include dollar amounts
        "must_not_contain": [],
        "min_results": 5,
        "check": "response includes donor names and amounts"
    },
    {
        "query": "Which lapsed donors in Virginia gave more than $5,000?",
        "must_contain": ["VA", "Virginia"],
        "must_not_contain": [],
        "check": "all donors listed are from VA and have last_gift_date > 2 years ago"
    },
    {
        "query": "Plan a fundraising trip to New York. Who should we meet?",
        "must_contain": ["New York", "NY", "NYC"],
        "must_not_contain": [],
        "check": "response includes ranked list with rationale for each person"
    },
    {
        "query": "How many subscribers have never donated?",
        "must_contain": [],
        "must_not_contain": [],
        "check": "response includes a number and mentions prospects or non-donors"
    },
    {
        "query": "Show me donors who gave stock or through a DAF",
        "must_contain": ["stock", "DAF", "donor-advised"],
        "must_not_contain": [],
        "check": "filters by giving_vehicle correctly"
    },
    {
        "query": "What does our donor pipeline look like?",
        "must_contain": ["active", "lapsed", "prospect"],
        "must_not_contain": [],
        "check": "gives breakdown by donor_status with counts"
    },
    {
        "query": "Who are the highest-potential prospects we should cultivate?",
        "must_contain": [],
        "must_not_contain": [],
        "check": "returns prospects sorted by engagement and wealth signals"
    },
    {
        "query": "Compare giving patterns between Virginia donors and out-of-state donors",
        "must_contain": ["Virginia", "VA"],
        "must_not_contain": [],
        "check": "provides comparison with summary statistics for both groups"
    },
    {
        "query": "What are best practices for re-engaging lapsed donors?",
        "must_contain": ["lapsed", "re-engage"],
        "must_not_contain": [],
        "check": "draws on fundraising knowledge base; mentions benchmarks or strategies from the KB"
    },
    {
        "query": "We're planning a trip to DC. Who should we meet and why?",
        "must_contain": ["DC", "Washington"],
        "must_not_contain": [],
        "check": "combines data query (DC-area donors) with best practice context (trip planning, center-out approach)"
    }
]
```

Note: behavioral tests require an API key and cost money. Include a --skip-llm flag to run only unit tests.

---

## Step 7: Write README.md

Include:
1. One-paragraph project description
2. Setup instructions (clone, install, set API key, generate data, run)
3. Screenshot or description of the UI
4. Architecture diagram (text-based, same as in CLAUDE.md)
5. How to run tests
6. Cost estimates per query
7. Known limitations
8. How students can extend this prototype

---

## Step 8: Create the build log

Create `docs/build_log.md` with dated entries documenting:
- What was built in each session
- Key design decisions and why
- Problems encountered and how they were solved
- Things that would need to change for production

This is a teaching artifact; students should see how a professional documents their development process.

---

## Implementation notes

### On mock data realism

The mock data generator is the foundation. Spend time making it realistic:
- Use the real IASC sample (data/sample_salesforce.csv) to calibrate distributions
- The power-law gift distribution is critical; a uniform random distribution would look nothing like real fundraising data
- Geographic clustering matters; IASC's donor base is concentrated in Virginia, the Northeast corridor, and a few other metro areas
- Temporal patterns matter; many gifts cluster around year-end (November-December)

### On the LLM integration

- Use Claude's native tool use (not string parsing or regex extraction)
- Allow Claude to call multiple tools per turn if needed
- Include the database schema summary in the system prompt so Claude knows what fields are available
- Keep the system prompt under 2000 tokens; move detailed field descriptions to tool parameter descriptions
- Log every API call with timestamps, token counts, and the tool calls made

### On cost management

At Sonnet pricing (~$3/M input, ~$15/M output tokens as of early 2025):
- A typical query with tool use costs $0.01-0.05
- The system prompt + schema + knowledge base is ~2500-3500 input tokens per call (knowledge base adds ~1500-2000)
- Budget for ~100 test queries during development: ~$3-8
- The token tracker (Step 4a) displays costs inline with each response and in the sidebar
- Use this data to compare Sonnet vs. Haiku cost/quality tradeoffs

### On the knowledge base

- The knowledge base is deliberately simple: markdown files loaded into the system prompt
- This is a "phase 1" approach; the architecture is designed for three upgrade paths:
  1. **RAG**: Chunk the documents, embed them, retrieve relevant chunks per query instead of loading everything
  2. **Claude Skill**: Package the knowledge as a skill with its own tool definitions (e.g., `lookup_best_practice(topic)`)
  3. **MCP tool**: Expose the knowledge base as an MCP server that Claude can query
- Keep the XML-style tags (`<fundraising_knowledge>`, `<iasc_context>`) even if you change the retrieval mechanism; they help Claude distinguish knowledge sources
- The knowledge base content should be factual and practitioner-oriented; avoid fabricated citations
- Students will be able to extend this by adding more documents or building the RAG pipeline

### On token tracking

- Every API call returns `response.usage.input_tokens` and `response.usage.output_tokens`; always capture these
- A single user question may trigger 2-5 API calls (initial + tool use round-trips); the tracker accumulates across all calls
- Display per-response usage inline (muted caption below the response) so users develop intuition for costs
- Display session totals in the sidebar
- This is a pedagogical feature: students should understand that every API call has a cost, and design decisions (model choice, system prompt size, knowledge base inclusion) affect that cost

### On error handling

- If Claude generates a tool call with invalid parameters, catch the error and return a helpful message
- If the database query returns no results, tell Claude so it can report this to the user
- If the API call fails (rate limit, network error), display a user-friendly error
- Never show raw Python tracebacks to the user

### What this prototype deliberately does NOT include

- Authentication or user accounts
- Real data integration (Salesforce API, MailChimp API, WealthEngine API)
- Data upload or editing capabilities
- Export to CSV/Excel
- Visualization dashboard (beyond basic inline tables)
- RAG over the knowledge base (currently injected into system prompt; RAG is a student project)
- Multi-user support
- Deployment to a cloud server

These are features the student teams will work on during the semester. The knowledge base and token tracker are designed as clean extension points.

# Build Log — IASC Donor Analytics Prototype

---

## 2026-02-25 — Initial build complete

### What was built

This prototype was constructed in four parallel workstreams:

**Workstream A (data layer)**
- `data/generate_mock_data.py`: Generates 300 synthetic donor records with realistic distributions across all fields. Produces three SQLite tables: `contacts`, `gifts`, and `interactions`. Gift amounts span $10 – $500,000, giving histories run from 1993 – 2025, and roughly 15% of contacts cluster in Virginia ZIP codes near Charlottesville (IASC's home base). Approximately 40% of contacts have NULL wealth scores (realistic for a small nonprofit without full WealthEngine coverage) and 15% have NULL email open rates.
- `data/data_dictionary.md`: Field-by-field documentation for all three tables, including source system (Salesforce / MailChimp / WealthEngine), data type, allowed values, and null rate.
- `data/sample_salesforce.csv`: 91 anonymized records from a real IASC Salesforce export, retained for reference and eventual validation.

**Workstream B (knowledge base)**
- `knowledge/fundraising_best_practices.md`: A practitioner reference covering donor segmentation (LYBUNT / SYBUNT), lapsed donor re-engagement benchmarks, major gift strategy, the Capacity-Affinity-Proximity (CAP) framework, email engagement benchmarks, and key fundraising metrics.
- `knowledge/iasc_context.md`: IASC-specific context — the development team (Andrew Westhouse, Rosemary Armato), the "center-out" cultivation philosophy, data system landscape (Salesforce + MailChimp + WealthEngine), known data quality issues, and The Hedgehog Review subscriber pipeline.
- `knowledge/README.md`: Documentation for the knowledge base directory explaining the injection approach and how to extend it.
- `src/knowledge.py`: Loader that reads both markdown files and formats them as XML-tagged sections for injection into the system prompt.

**Workstream C (query functions)**
- `src/queries.py`: Seven parameterized query functions that serve as Claude's tools: `search_donors`, `get_donor_detail`, `get_summary_statistics`, `get_geographic_distribution`, `get_lapsed_donors`, `get_prospects_by_potential`, and `plan_fundraising_trip`. All return `{"results": [...], "count": int, "summary": str}`. The trip planning function uses a composite scoring formula (giving history 30%, wealth 20%, recency 20%, engagement 15%, subscription 15%) computed in Python after a SQL fetch for transparency.
- `tests/test_queries.py`: 45+ unit tests covering all query functions, edge cases, SQL injection guards, and result structure validation. No API calls; runs entirely against the local SQLite database.

**Workstream D (LLM integration + UI)**
- `src/config.py`: Central configuration — paths, model IDs, token limits, UI strings.
- `src/token_tracker.py`: `APICall`, `ResponseUsage`, and `SessionTracker` dataclasses for tracking per-call and per-session token usage and costs.
- `src/prompts.py`: System prompt assembly — base instructions, schema summary, and knowledge base content concatenated at call time.
- `src/llm.py`: Claude API integration with the tool-use conversation loop. `get_response()` drives the loop: call the API, execute any requested tools, append results, repeat until `end_turn`.
- `src/app.py`: Streamlit chat application with sidebar stats, sample questions, model selector, session usage summary, and inline token cost display per response.
- `tests/test_scenarios.py`: 14 behavioral tests that send real natural language questions through the full pipeline and assert response quality (mentions geography, includes dollar amounts, references fundraising concepts, etc.). Marked `llm`; excluded by default from `pytest tests/ -k "not llm"`.
- `README.md`: Full project documentation.
- `docs/build_log.md`: This file.

---

### Key design decisions

**Tool use over RAG for tabular data**

Donor data is structured and well-defined: every interesting fact is in a column. The alternative — embedding donor records and retrieving by semantic similarity — would be slower, more expensive, and less precise. A fundraiser asking "which lapsed donors in Virginia gave more than $5,000?" needs an exact answer, not the most semantically similar document chunks. Tool use lets Claude decide which filters to apply; Python executes a deterministic SQL query. The result is correct by construction.

This decision simplifies the architecture substantially: no vector store, no embedding API, no chunking strategy. The tradeoff is that unstructured notes (the `notes` field in the contacts table) are not searchable by content. If notes become important, a hybrid approach (SQL for structured fields + semantic search for notes) would be the next step.

**Knowledge base injection into the system prompt**

Fundraising best practices and IASC-specific context are loaded from markdown files and appended to the system prompt on every API call. This is the simplest possible approach and works well for a knowledge base in the 2,000 – 5,000 word range. The main costs are:

1. Token cost: the knowledge base consumes roughly 3,000 – 4,000 tokens on every call, adding ~$0.01 per query on Sonnet. Acceptable for a prototype; meaningful at scale.
2. Staleness: the markdown files must be updated manually as IASC's practices evolve.

The `load_knowledge_base()` function in `src/knowledge.py` is deliberately the single integration point. Replacing it with a RAG retrieval function requires changing only that one function; the rest of the system is unaffected. This makes the current approach a reasonable starting point that does not foreclose the RAG path.

**Token tracking rationale**

The token tracker was built as a first-class component rather than an afterthought. Reasons:

1. The project has a real budget constraint (~$500 for a semester across 28 students). Making costs visible prevents runaway spending.
2. Graduate students building the production version need to develop intuition for what different query patterns cost. Displaying tokens and dollars inline with every response is the fastest way to build that intuition.
3. The `SessionTracker` enables end-of-session accounting, useful for deciding when to switch from Sonnet to Haiku during development.

**Parallel workstream build strategy**

The four workstreams (A: data, B: knowledge, C: queries, D: LLM+UI) are independent of each other. Building them in parallel means the critical path is max(A, B, C) + D rather than A + B + C + D. In practice, workstream D takes the longest (more files, more integration) so the parallelism is well-matched.

Workstream D has a hard dependency on A (needs `donors.db`), B (needs `knowledge.py`), and C (needs `queries.py`). This dependency structure was documented upfront in `CLAUDE.md` so subagents could be dispatched correctly.

**No LangChain or LlamaIndex**

The tool-use conversation loop is about 60 lines of code in `src/llm.py`. LangChain would add a layer of abstraction over that 60-line loop and introduce ~100 indirect dependencies that students would have to understand to debug the system. The Anthropic SDK is the only dependency for the LLM layer. This is consistent with the teaching goal: every part of the system should be legible to a graduate student in the first week.

---

### Known issues and production gaps

**Real data integration**

The most important gap. The prototype runs on synthetic data. Production requires:
- Salesforce integration via the `simple_salesforce` Python library. The Salesforce export schema matches the mock data schema closely (Contact ID, gift dates, amounts, etc.), so `src/queries.py` functions would need minimal changes.
- MailChimp integration for live email open rates and click dates, replacing the mock values.
- WealthEngine integration for real wealth scores via the WealthEngine REST API.

All three integrations should write to the same SQLite schema (or a production Postgres database) so `queries.py` functions do not change.

**Authentication**

The Streamlit app has no login screen. This is acceptable for a local prototype with mock data. Before deployment with real donor data, add authentication. Options in ascending order of complexity: Streamlit Community Cloud's built-in auth, a simple password via `st.secrets`, or an OAuth integration.

**No data export**

Development officers frequently need to export query results to Excel or CSV for use in Salesforce or for sharing with colleagues. Adding a "Download as CSV" button below each response requires (a) parsing the structured tool result from the conversation, and (b) `st.download_button()`. This is a three-hour feature for a future iteration.

**Conversation persistence**

Closing the browser tab loses the session. For production, conversation history should be persisted to a database (SQLite or Postgres) keyed on user ID.

**Knowledge base freshness**

The markdown files in `knowledge/` must be updated manually. If the knowledge base grows to dozens of documents, full-document injection becomes expensive and a RAG approach (embed documents, retrieve relevant passages per query) becomes necessary. The `load_knowledge_base()` function is the designed replacement point.

**WealthEngine score coverage**

Approximately 40% of contacts have NULL wealth scores in the mock data (realistic for a small nonprofit). The query functions handle NULLs defensively, but the system should surface a clear caveat to users when scores are missing for candidates in their results.

---

### Teaching notes

This prototype is designed to be a teaching artifact as much as a working tool. Key learning objectives it demonstrates:

1. **Tool use / function calling.** The `get_response()` loop in `src/llm.py` is a clean implementation of the multi-turn tool-use pattern. Students can trace a single query from user input through API call, tool execution, result injection, and final response in about 80 lines of code.

2. **Structured data + LLMs.** The decision to use SQL queries rather than RAG illustrates that LLMs are not always the right tool for retrieval. When data is tabular and queries are precise, parameterized SQL is more reliable, cheaper, and easier to debug.

3. **System prompt engineering.** The `build_system_prompt()` function in `src/prompts.py` shows how a system prompt is assembled from multiple components: base instructions, schema context, and domain knowledge. Students can experiment with removing components and observing the effect on response quality.

4. **Cost-aware development.** The token tracker makes the economics of LLM APIs concrete. Students can see that a Sonnet query with tool use costs $0.02 – $0.05 and understand why the class has a $500 budget constraint.

5. **Testing LLM applications.** `tests/test_scenarios.py` shows a pragmatic approach to behavioral testing: assert observable properties of the response (contains geography, contains dollar amounts, mentions fundraising concepts) rather than exact string matching. These tests are not exhaustive but catch regressions in the most common failure modes.

6. **Separation of concerns.** The five source files (`config`, `token_tracker`, `knowledge`, `prompts`, `queries`, `llm`, `app`) each have a single clear responsibility. Students building the production version can work on one file without needing to understand all the others.

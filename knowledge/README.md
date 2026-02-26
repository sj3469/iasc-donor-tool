# Knowledge Base

This directory contains reference documents that are loaded into the AI system's context at runtime.

## What these files are

- `fundraising_best_practices.md`: A practitioner's reference covering donor segmentation, lapsed donor re-engagement, major gift strategy, prospect research, email engagement benchmarks, and key metrics.
- `iasc_context.md`: IASC-specific organizational context — who the development team is, what data systems they use, what their donor base looks like, and known data quality limitations.

## How they are used

The file `src/knowledge.py` reads both documents and formats them as XML-tagged sections, which are then injected into the Claude system prompt at the start of each session. Claude uses these documents to give advice that is grounded in fundraising best practices and calibrated to IASC's specific situation.

## How to add or update content

Edit the markdown files directly. The loader (`src/knowledge.py`) reads them fresh on each call, so changes take effect immediately without restarting the app. New documents can be added by editing `knowledge.py` to load and tag the additional file.

## Future directions

The current approach (full-document injection into the system prompt) is simple and works well for a small knowledge base. As the document collection grows, consider:

- **RAG pipeline:** Chunk documents, embed them, and retrieve only the most relevant passages per query. Reduces token cost and improves precision for large collections.
- **Claude Skill:** Package the knowledge base as a reusable skill with its own tools and retrieval logic, callable across multiple applications.
- **MCP server:** Expose the knowledge base as a Model Context Protocol server, allowing Claude to query it on demand rather than loading everything upfront.

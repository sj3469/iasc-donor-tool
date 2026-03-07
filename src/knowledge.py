"""
Knowledge base loader for fundraising best practices and IASC context.

Currently: reads markdown files and injects them into the system prompt.
Future: could be replaced with retrieval-based lookup or a dedicated tool.
"""

from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def load_knowledge_base() -> str:
    """Load all knowledge base documents and format them for the system prompt."""
    sections = []

    practices_path = KNOWLEDGE_DIR / "fundraising_best_practices.md"
    if practices_path.exists():
        content = practices_path.read_text(encoding="utf-8")
        sections.append(
            f"<fundraising_knowledge>\n{content}\n</fundraising_knowledge>"
        )

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
        "The following reference materials are available to inform responses. "
        "Use them when relevant, but prioritize actual donor database results "
        "over general best practices.\n\n"
        + "\n\n".join(sections)
    )


def get_knowledge_token_estimate() -> int:
    """Estimate the token footprint of the knowledge base."""
    total_words = 0
    for filename in ["fundraising_best_practices.md", "iasc_context.md"]:
        filepath = KNOWLEDGE_DIR / filename
        if filepath.exists():
            total_words += len(filepath.read_text(encoding="utf-8").split())
    return int(total_words * 0.75)


"""Builtin skills — prompt injection definitions.

Each builtin skill is a dict with:
- ``identifier`` — unique skill ID
- ``name`` — display name
- ``description`` — what the skill does
- ``prompt`` — the system prompt text to inject
- ``tools`` — optional list of OpenAI function schemas

These are auto-provisioned for new users and can be referenced by
``Agent.plugins`` as skill identifiers.
"""

from __future__ import annotations

from typing import Any


# ── Artifacts Skill ──────────────────────────────────────────────────

ARTIFACTS_PROMPT = """\
You have the ability to create and reference artifacts during conversations. \
Artifacts are for substantial, self-contained content that users might modify \
or reuse, displayed in a separate UI window for clarity.

# Good Artifacts
- Original creative writing (stories, poems, essays)
- In-depth explanations or tutorials
- Code snippets and scripts (>15 lines)
- Structured data (tables, lists, configurations)
- Interactive components (HTML/React)

# Bad Artifacts (use normal messages instead)
- Brief responses or simple answers
- Informational/explanatory content
- Content that depends heavily on conversational context
- Content that is primarily an answer to a question

# Usage
When you create an artifact, wrap it in opening and closing `<lobeArtifact>` tags with these attributes:
- `identifier`: A unique kebab-case ID (e.g. "my-code-snippet")
- `type`: The artifact content type ("text/markdown", "application/code", "text/html", "image/svg+xml", "application/react")
- `title`: A brief title
- `language`: Programming language (for code artifacts only)

Example:
<lobeArtifact identifier="example-code" type="application/code" title="Hello World" language="python">
print("Hello, World!")
</lobeArtifact>
"""

ARTIFACTS_SKILL: dict[str, Any] = {
    "identifier": "lobe-artifacts",
    "name": "Artifacts",
    "description": "Enable the assistant to create rich artifacts (code, documents, SVGs, React components) "
    "displayed in a separate panel.",
    "prompt": ARTIFACTS_PROMPT,
    "tools": [],
}


# ── Web Search Skill ────────────────────────────────────────────────

WEB_SEARCH_SKILL: dict[str, Any] = {
    "identifier": "lobe-web-search",
    "name": "Web Search",
    "description": "Allow the assistant to search the web for current information.",
    "prompt": "You have access to a web search tool. When the user asks about current events, "
    "recent information, or anything that may require up-to-date data, use the web_search tool.",
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ],
}


# ── Knowledge Base Skill ─────────────────────────────────────────────

KNOWLEDGE_BASE_SKILL: dict[str, Any] = {
    "identifier": "lobe-knowledge-base",
    "name": "Knowledge Base",
    "description": "Allow the assistant to search the user's knowledge bases for relevant context.",
    "prompt": "You have access to the user's knowledge bases. When the user asks about content from "
    "their uploaded files or documents, use the knowledge_base_search tool to find relevant information.",
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "knowledge_base_search",
                "description": "Search the user's knowledge bases.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query to search",
                        },
                        "knowledge_base_id": {
                            "type": "string",
                            "description": "Optional KB ID to scope search",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ],
}


# ── All builtin skills ───────────────────────────────────────────────

BUILTIN_SKILLS: list[dict[str, Any]] = [
    ARTIFACTS_SKILL,
    WEB_SEARCH_SKILL,
    KNOWLEDGE_BASE_SKILL,
]


def get_builtin_skill(identifier: str) -> dict[str, Any] | None:
    """Look up a builtin skill by identifier."""
    for skill in BUILTIN_SKILLS:
        if skill["identifier"] == identifier:
            return skill
    return None


def list_builtin_skill_identifiers() -> list[str]:
    return [s["identifier"] for s in BUILTIN_SKILLS]

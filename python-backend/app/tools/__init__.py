"""Builtin tools package.

Import this package to auto-register all builtin tools with the registry.
"""

from app.tools.registry import (
    get_all_tool_schemas,
    get_context_handler,
    get_handler,
    get_tool,
    register,
    register_context_handler,
    tool_names,
)

# Import tool modules to trigger @register decorators
import app.tools.calculator  # noqa: F401
import app.tools.memory_tool  # noqa: F401
import app.tools.knowledge_base_tool  # noqa: F401
import app.tools.agent_builder  # noqa: F401
import app.tools.web_search  # noqa: F401
import app.tools.url_crawler  # noqa: F401
import app.tools.dalle_image_gen  # noqa: F401
import app.tools.code_interpreter  # noqa: F401
import app.tools.user_interaction  # noqa: F401
import app.tools.topic_reference  # noqa: F401
import app.tools.skills  # noqa: F401
import app.tools.skill_store  # noqa: F401
import app.tools.activator  # noqa: F401
import app.tools.gtd_tool  # noqa: F401
import app.tools.task_tool  # noqa: F401
import app.tools.brief_tool  # noqa: F401
import app.tools.lobe_agent_tool  # noqa: F401
import app.tools.agent_documents_tool  # noqa: F401
import app.tools.notebook_tool  # noqa: F401

__all__ = [
    "get_all_tool_schemas",
    "get_context_handler",
    "get_handler",
    "get_tool",
    "register",
    "register_context_handler",
    "tool_names",
]

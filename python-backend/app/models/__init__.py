# Re-export all models so Alembic can discover them via a single import.
from app.models._helpers import *  # noqa: F401,F403
from app.models.user import *  # noqa: F401,F403
from app.models.agent import *  # noqa: F401,F403
from app.models.session import *  # noqa: F401,F403
from app.models.message import *  # noqa: F401,F403
from app.models.topic import *  # noqa: F401,F403
from app.models.file import *  # noqa: F401,F403
from app.models.knowledge import *  # noqa: F401,F403
from app.models.rag import *  # noqa: F401,F403
from app.models.ai_infra import *  # noqa: F401,F403
from app.models.memory import *  # noqa: F401,F403
from app.models.skill import *  # noqa: F401,F403
from app.models.rbac import *  # noqa: F401,F403

# Non-MVP (schema only)
from app.models.chat_group import *  # noqa: F401,F403
from app.models.message_ext import *  # noqa: F401,F403
from app.models.topic_ext import *  # noqa: F401,F403
from app.models.document_ext import *  # noqa: F401,F403
from app.models.rag_ext import *  # noqa: F401,F403
from app.models.rag_eval import *  # noqa: F401,F403
from app.models.task import *  # noqa: F401,F403
from app.models.agent_ops import *  # noqa: F401,F403
from app.models.agent_eval import *  # noqa: F401,F403
from app.models.generation import *  # noqa: F401,F403
from app.models.persona import *  # noqa: F401,F403
from app.models.misc import *  # noqa: F401,F403

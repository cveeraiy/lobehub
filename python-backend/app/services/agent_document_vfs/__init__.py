"""Agent Document VFS — virtual filesystem over agent documents + mounted skill subtrees."""

from app.services.agent_document_vfs.service import AgentDocumentVfsService
from app.services.agent_document_vfs.types import (
    AgentDocumentMountInfo,
    AgentDocumentNode,
    AgentDocumentReadResult,
    AgentDocumentStats,
    AgentDocumentTrashEntry,
)
from app.services.agent_document_vfs.errors import AgentDocumentVfsError

__all__ = [
    "AgentDocumentVfsService",
    "AgentDocumentMountInfo",
    "AgentDocumentNode",
    "AgentDocumentReadResult",
    "AgentDocumentStats",
    "AgentDocumentTrashEntry",
    "AgentDocumentVfsError",
]

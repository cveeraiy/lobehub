"""Types for the Agent Document VFS layer.

Mirrors TypeScript: src/server/services/agentDocumentVfs/types.ts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntFlag
from typing import Any, Literal, Optional


# ── Access bitmask ──────────────────────────────────────────────────

class AgentAccess(IntFlag):
    EXECUTE = 1     # bit 0
    READ    = 2     # bit 1
    WRITE   = 4     # bit 2
    LIST    = 8     # bit 3
    DELETE  = 16    # bit 4


FULL_ACCESS = (
    AgentAccess.EXECUTE
    | AgentAccess.READ
    | AgentAccess.WRITE
    | AgentAccess.LIST
    | AgentAccess.DELETE
)

DOCUMENT_FOLDER_TYPE = "agent/folder"


# ── VFS node types ──────────────────────────────────────────────────

@dataclass
class AgentDocumentMountInfo:
    driver: str
    namespace: Optional[str] = None
    source: Optional[str] = None


@dataclass
class AgentDocumentNode:
    id: str
    name: str
    path: str
    type: Literal["directory", "file"]
    mode: int
    mount: Optional[AgentDocumentMountInfo] = None
    agent_document_id: Optional[str] = None
    document_id: Optional[str] = None
    size: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "mode": self.mode,
        }
        if self.mount:
            d["mount"] = {"driver": self.mount.driver, "namespace": self.mount.namespace, "source": self.mount.source}
        if self.agent_document_id:
            d["agentDocumentId"] = self.agent_document_id
        if self.document_id:
            d["documentId"] = self.document_id
        if self.size is not None:
            d["size"] = self.size
        if self.created_at:
            d["createdAt"] = self.created_at.isoformat()
        if self.updated_at:
            d["updatedAt"] = self.updated_at.isoformat()
        return d


@dataclass
class AgentDocumentStats(AgentDocumentNode):
    content_type: Optional[str] = None
    deleted_at: Optional[datetime] = None
    delete_reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.content_type:
            d["contentType"] = self.content_type
        if self.deleted_at:
            d["deletedAt"] = self.deleted_at.isoformat()
        if self.delete_reason:
            d["deleteReason"] = self.delete_reason
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class AgentDocumentTrashEntry(AgentDocumentStats):
    pass


@dataclass
class AgentDocumentReadResult:
    content: str
    path: str
    content_type: Optional[str] = None


@dataclass
class AgentDocumentListOptions:
    cursor: Optional[str] = None
    detail: Literal["basic", "full"] = "basic"
    limit: Optional[int] = None


@dataclass
class AgentDocumentVfsContext:
    agent_id: str
    topic_id: Optional[str] = None

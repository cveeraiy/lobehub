"""VFS error types.

Mirrors TypeScript: src/server/services/agentDocumentVfs/errors.ts
"""

from __future__ import annotations

from typing import Literal

AgentDocumentVfsErrorCode = Literal[
    "BAD_REQUEST",
    "CONFLICT",
    "FORBIDDEN",
    "METHOD_NOT_SUPPORTED",
    "NOT_FOUND",
]


class AgentDocumentVfsError(Exception):
    """Typed error for VFS and mounted-subtree operation failures."""

    code: AgentDocumentVfsErrorCode

    def __init__(self, message: str, code: AgentDocumentVfsErrorCode) -> None:
        super().__init__(message)
        self.code = code

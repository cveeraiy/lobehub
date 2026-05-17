"""Shared helpers for SQLModel table definitions.

Mirrors packages/database/src/schemas/_helpers.ts and utils/idGenerator.ts.
"""

from __future__ import annotations

import string
from datetime import datetime, timezone
from typing import Optional

from nanoid import generate as nanoid_generate
from sqlalchemy import ARRAY, Column, Index, text
from sqlalchemy.dialects.postgresql import JSON, TEXT
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field

# ── Nanoid helpers ──────────────────────────────────────────────────────────

_ALPHABET = string.ascii_letters + string.digits  # a-zA-Z0-9


def create_nanoid(size: int = 8) -> str:
    return nanoid_generate(_ALPHABET, size)


_PREFIXES: dict[str, str] = {
    "agentCronJobs": "cron",
    "agentSkills": "skl",
    "briefs": "brf",
    "taskComments": "cmt",
    "tasks": "task",
    "agents": "agt",
    "budget": "bgt",
    "chatGroups": "cg",
    "documents": "docs",
    "evalBenchmarks": "evb",
    "evalDatasets": "ds",
    "evalRuns": "run",
    "evalTestCases": "case",
    "files": "file",
    "generationBatches": "gb",
    "generationTopics": "gt",
    "generations": "gen",
    "knowledgeBases": "kb",
    "memory": "mem",
    "messageGroups": "mg",
    "messages": "msg",
    "plugins": "plg",
    "sessionGroups": "sg",
    "sessions": "ssn",
    "threads": "thd",
    "topics": "tpc",
    "user": "user",
}


def id_generator(namespace: str, size: int = 12) -> str:
    prefix = _PREFIXES.get(namespace)
    if prefix is None:
        raise ValueError(f"Invalid namespace: {namespace}")
    return f"{prefix}_{create_nanoid(size)}"


def inbox_session_id(user_id: str) -> str:
    return f"ssn_inbox_{user_id}"


# ── Timestamp defaults ──────────────────────────────────────────────────────


def _utcnow() -> datetime:
    """Naive UTC timestamp — matches TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def created_at_field() -> datetime:
    """Use as: `created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs=...)`"""
    return Field(
        default_factory=_utcnow,
        sa_column_kwargs={"server_default": text("now()")},
        nullable=False,
    )


def updated_at_field() -> datetime:
    return Field(
        default_factory=_utcnow,
        sa_column_kwargs={
            "server_default": text("now()"),
            "onupdate": _utcnow,
        },
        nullable=False,
    )


def accessed_at_field() -> datetime:
    return Field(
        default_factory=_utcnow,
        sa_column_kwargs={
            "server_default": text("now()"),
            "onupdate": _utcnow,
        },
        nullable=False,
    )


# ── pgvector column type ───────────────────────────────────────────────────


class VectorType(UserDefinedType):
    """SQLAlchemy column type for pgvector `vector(N)`.

    Usage in SQLModel:
        embedding: Optional[list[float]] = Field(
            default=None,
            sa_column=Column(VectorType(1024)),
        )
    """

    cache_ok = True

    def __init__(self, dimensions: int = 1024):
        self.dimensions = dimensions

    def get_col_spec(self) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return f"[{','.join(str(v) for v in value)}]"
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                return [float(v) for v in value.strip("[]").split(",")]
            return list(value)
        return process


def hnsw_index(column_name: str, table_name: str, *, op: str = "vector_cosine_ops") -> Index:
    """Create an HNSW index for a vector column."""
    return Index(
        f"{table_name}_{column_name}_index",
        column_name,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={column_name: op},
    )


# ── Column type helpers ────────────────────────────────────────────────────


def json_column(name: str, *, nullable: bool = True) -> Column:
    """JSONB column for dict/list fields that SQLModel can't auto-map."""
    return Column(name, JSON, nullable=nullable)


def text_array_column(name: str, *, nullable: bool = True) -> Column:
    """text[] column for list[str] fields."""
    return Column(name, ARRAY(TEXT()), nullable=nullable)

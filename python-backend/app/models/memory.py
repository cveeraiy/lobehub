"""User memory tables (5 layers + base).

Canonical database models for user memory tables.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, Index, Numeric, text
from sqlmodel import Field, SQLModel

from app.models._helpers import VectorType, _utcnow, id_generator, json_column, text_array_column

# ── user_memories (base layer) ──────────────────────────────────────────────


class UserMemory(SQLModel, table=True):
    __tablename__ = "user_memories"

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)

    memory_category: Optional[str] = Field(default=None, max_length=255)
    memory_layer: Optional[str] = Field(default=None, max_length=255)
    memory_type: Optional[str] = Field(default=None, max_length=255)
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    summary_vector_1024: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("summary_vector_1024", VectorType(1024)),
    )
    details: Optional[str] = None
    details_vector_1024: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("details_vector_1024", VectorType(1024)),
    )

    status: Optional[str] = Field(default=None, max_length=255)
    accessed_count: Optional[int] = Field(default=0, sa_column=Column(BigInteger, nullable=True))
    last_accessed_at: datetime = Field(default_factory=_utcnow)
    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_memories_contexts ──────────────────────────────────────────────────


class UserMemoryContext(SQLModel, table=True):
    __tablename__ = "user_memories_contexts"
    __table_args__ = (
        Index("user_memories_contexts_type_index", "type"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    user_memory_ids: Optional[list[str]] = Field(default=None, sa_column=json_column("user_memory_ids"))

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    associated_objects: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("associated_objects"))
    associated_subjects: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("associated_subjects"))

    title: Optional[str] = None
    description: Optional[str] = None
    description_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("description_vector", VectorType(1024)),
    )

    type: Optional[str] = Field(default=None, max_length=255)
    current_status: Optional[str] = None

    score_impact: Optional[float] = Field(default=0, sa_column=Column(Numeric, nullable=True))
    score_urgency: Optional[float] = Field(default=0, sa_column=Column(Numeric, nullable=True))

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_memories_preferences ───────────────────────────────────────────────


class UserMemoryPreference(SQLModel, table=True):
    __tablename__ = "user_memories_preferences"

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    user_memory_id: Optional[str] = Field(default=None, max_length=255, foreign_key="user_memories.id")

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    conclusion_directives: Optional[str] = None
    conclusion_directives_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("conclusion_directives_vector", VectorType(1024)),
    )

    type: Optional[str] = Field(default=None, max_length=255)
    suggestions: Optional[str] = None
    score_priority: Optional[float] = Field(default=0, sa_column=Column(Numeric, nullable=True))

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_memories_activities ────────────────────────────────────────────────


class UserMemoryActivity(SQLModel, table=True):
    __tablename__ = "user_memories_activities"
    __table_args__ = (
        Index("user_memories_activities_type_index", "type"),
        Index("user_memories_activities_status_index", "status"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    user_memory_id: Optional[str] = Field(default=None, max_length=255, foreign_key="user_memories.id")

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    type: str = Field(nullable=False, max_length=255)
    status: str = Field(default="pending", max_length=255)
    timezone: Optional[str] = Field(default=None, max_length=255)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    associated_objects: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("associated_objects"))
    associated_subjects: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("associated_subjects"))
    associated_locations: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("associated_locations"))

    notes: Optional[str] = None
    narrative: Optional[str] = None
    narrative_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("narrative_vector", VectorType(1024)),
    )
    feedback: Optional[str] = None
    feedback_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("feedback_vector", VectorType(1024)),
    )

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_memories_identities ────────────────────────────────────────────────


class UserMemoryIdentity(SQLModel, table=True):
    __tablename__ = "user_memories_identities"
    __table_args__ = (
        Index("user_memories_identities_type_index", "type"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    user_memory_id: Optional[str] = Field(default=None, max_length=255, foreign_key="user_memories.id")

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    type: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    description_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("description_vector", VectorType(1024)),
    )
    episodic_date: Optional[datetime] = None
    relationship: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = None

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_memories_experiences ───────────────────────────────────────────────


class UserMemoryExperience(SQLModel, table=True):
    __tablename__ = "user_memories_experiences"
    __table_args__ = (
        Index("user_memories_experiences_type_index", "type"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("memory"),
        primary_key=True,
        max_length=255,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    user_memory_id: Optional[str] = Field(default=None, max_length=255, foreign_key="user_memories.id")

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    tags: Optional[list[str]] = Field(default=None, sa_column=text_array_column("tags"))

    type: Optional[str] = Field(default=None, max_length=255)
    situation: Optional[str] = None
    situation_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("situation_vector", VectorType(1024)),
    )
    reasoning: Optional[str] = None
    possible_outcome: Optional[str] = None
    action: Optional[str] = None
    action_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("action_vector", VectorType(1024)),
    )
    key_learning: Optional[str] = None
    key_learning_vector: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("key_learning_vector", VectorType(1024)),
    )

    score_confidence: Optional[float] = Field(default=0)

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

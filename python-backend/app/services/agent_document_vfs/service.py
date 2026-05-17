"""Agent Document VFS Service.

Unified filesystem view for ordinary agent documents.  Skill mounts are
surfaced as synthetic read-only directories; write-through to skill storage
is **not** implemented yet (requires the SkillMount subsystem).

Mirrors TypeScript: src/server/services/agentDocumentVfs/index.ts
"""

from __future__ import annotations

import logging
import posixpath
import re
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, asc, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_ops import AgentDocument
from app.models.file import Document

from .errors import AgentDocumentVfsError
from .types import (
    DOCUMENT_FOLDER_TYPE,
    FULL_ACCESS,
    AgentAccess,
    AgentDocumentListOptions,
    AgentDocumentMountInfo,
    AgentDocumentNode,
    AgentDocumentReadResult,
    AgentDocumentStats,
    AgentDocumentTrashEntry,
)

logger = logging.getLogger(__name__)

LOBE_PATH = ".lobe"
DEFAULT_LIST_LIMIT = 200
MAX_SUBTREE_CAP = 500
_SEGMENT_RE = re.compile(r'^[^/\x00]+$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_path(raw: str) -> str:
    """Normalize a VFS path to a canonical form (no leading / or trailing /)."""
    p = raw.replace("\\", "/").strip()
    if p in (".", "", "/"):
        return "."
    parts = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts) if parts else "."


def _validate_segment(segment: str) -> None:
    if not segment or not _SEGMENT_RE.match(segment):
        raise AgentDocumentVfsError(
            f"Invalid path segment: {segment!r}", "BAD_REQUEST"
        )


def _split_path(path: str) -> tuple[Optional[str], str]:
    """Split normalised path into (parent_dir, basename).

    Returns (None, name) for root-level entries, (parent, name) for nested.
    """
    parts = path.split("/")
    name = parts[-1]
    parent = "/".join(parts[:-1]) if len(parts) > 1 else None
    return parent, name


class AgentDocumentVfsService:
    """Virtual filesystem over agent_documents + documents tables."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._user_id = user_id

    # ── helpers ──────────────────────────────────────────────────────

    async def _resolve_parent_document_id(
        self, agent_id: str, parent_path: Optional[str]
    ) -> Optional[str]:
        """Walk the path segments from root to find the document_id of the
        directory at *parent_path*."""
        if parent_path is None:
            return None

        parts = parent_path.split("/")
        current_parent_id: Optional[str] = None
        for seg in parts:
            stmt = (
                select(Document.id)
                .join(AgentDocument, AgentDocument.document_id == Document.id)
                .where(
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.agent_id == agent_id,
                    Document.filename == seg,
                    Document.parent_id == current_parent_id
                    if current_parent_id
                    else Document.parent_id.is_(None),
                    AgentDocument.deleted_at.is_(None),
                )
                .limit(1)
            )
            result = await self._db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            current_parent_id = row
        return current_parent_id

    async def _get_full_path(self, agent_id: str, document_id: str) -> str:
        """Walk parentId chain to reconstruct full VFS path."""
        parts: list[str] = []
        current_id: Optional[str] = document_id
        safety = 0
        while current_id and safety < 50:
            safety += 1
            stmt = select(Document.filename, Document.parent_id).where(
                Document.id == current_id, Document.user_id == self._user_id
            )
            result = await self._db.execute(stmt)
            row = result.one_or_none()
            if not row:
                break
            parts.append(row.filename or "")
            current_id = row.parent_id
        parts.reverse()
        return "/".join(parts)

    def _node_from_row(
        self,
        ad: AgentDocument,
        doc: Document,
        path: str,
    ) -> AgentDocumentNode:
        is_dir = doc.file_type == DOCUMENT_FOLDER_TYPE
        return AgentDocumentNode(
            id=ad.id,
            name=doc.filename or doc.title or "",
            path=path,
            type="directory" if is_dir else "file",
            mode=ad.access_self,
            agent_document_id=ad.id,
            document_id=doc.id,
            size=doc.total_char_count if not is_dir else None,
            created_at=ad.created_at,
            updated_at=ad.updated_at,
        )

    def _stats_from_row(
        self,
        ad: AgentDocument,
        doc: Document,
        path: str,
    ) -> AgentDocumentStats:
        is_dir = doc.file_type == DOCUMENT_FOLDER_TYPE
        return AgentDocumentStats(
            id=ad.id,
            name=doc.filename or doc.title or "",
            path=path,
            type="directory" if is_dir else "file",
            mode=ad.access_self,
            agent_document_id=ad.id,
            document_id=doc.id,
            size=doc.total_char_count if not is_dir else None,
            created_at=ad.created_at,
            updated_at=ad.updated_at,
            content_type=doc.file_type,
            deleted_at=ad.deleted_at,
            delete_reason=ad.delete_reason,
            metadata=getattr(doc, "metadata_", None),
        )

    # ── list ─────────────────────────────────────────────────────────

    async def list(
        self,
        agent_id: str,
        path: str = ".",
        options: Optional[AgentDocumentListOptions] = None,
    ) -> list[dict[str, Any]]:
        """List VFS entries under *path*."""
        opts = options or AgentDocumentListOptions()
        norm = _normalize_path(path)
        limit = opts.limit or DEFAULT_LIST_LIMIT
        offset = int(opts.cursor) if opts.cursor else 0

        parent_doc_id: Optional[str] = None
        if norm != ".":
            parent_doc_id = await self._resolve_parent_document_id(agent_id, norm)
            if parent_doc_id is None:
                raise AgentDocumentVfsError(
                    f"Directory not found: {norm}", "NOT_FOUND"
                )

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.deleted_at.is_(None),
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
            )
            .order_by(asc(AgentDocument.created_at), asc(AgentDocument.id))
            .offset(offset)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        nodes: list[dict[str, Any]] = []
        for ad, doc in rows:
            child_name = doc.filename or doc.title or ""
            child_path = f"{norm}/{child_name}" if norm != "." else child_name
            if opts.detail == "full":
                node = self._stats_from_row(ad, doc, child_path)
            else:
                node = self._node_from_row(ad, doc, child_path)
            nodes.append(node.to_dict())

        return nodes

    # ── stat ─────────────────────────────────────────────────────────

    async def stat(
        self, agent_id: str, path: str
    ) -> dict[str, Any]:
        """Return detailed stats for a single VFS path."""
        norm = _normalize_path(path)
        if norm == ".":
            return AgentDocumentStats(
                id="root",
                name=".",
                path=".",
                type="directory",
                mode=int(FULL_ACCESS),
            ).to_dict()

        parent_dir, name = _split_path(norm)
        parent_doc_id = await self._resolve_parent_document_id(agent_id, parent_dir) if parent_dir else None

        if parent_dir and parent_doc_id is None:
            raise AgentDocumentVfsError(f"Path not found: {norm}", "NOT_FOUND")

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == name,
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise AgentDocumentVfsError(f"Path not found: {norm}", "NOT_FOUND")

        ad, doc = row
        return self._stats_from_row(ad, doc, norm).to_dict()

    # ── read ─────────────────────────────────────────────────────────

    async def read(self, agent_id: str, path: str) -> AgentDocumentReadResult:
        """Read file content at *path*."""
        norm = _normalize_path(path)
        parent_dir, name = _split_path(norm)
        parent_doc_id = await self._resolve_parent_document_id(agent_id, parent_dir) if parent_dir else None

        if parent_dir and parent_doc_id is None:
            raise AgentDocumentVfsError(f"Path not found: {norm}", "NOT_FOUND")

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == name,
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise AgentDocumentVfsError(f"Path not found: {norm}", "NOT_FOUND")

        ad, doc = row
        if doc.file_type == DOCUMENT_FOLDER_TYPE:
            raise AgentDocumentVfsError(
                f"Cannot read a directory: {norm}", "BAD_REQUEST"
            )

        if not (ad.access_self & AgentAccess.READ):
            raise AgentDocumentVfsError(f"Read access denied: {norm}", "FORBIDDEN")

        return AgentDocumentReadResult(
            content=doc.content or "",
            path=norm,
            content_type=doc.file_type,
        )

    # ── write ────────────────────────────────────────────────────────

    async def write(
        self,
        agent_id: str,
        path: str,
        content: str,
        *,
        file_type: str = "agent/document",
        title: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        editor_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create or overwrite a file at *path*."""
        norm = _normalize_path(path)
        if norm == ".":
            raise AgentDocumentVfsError("Cannot write to root", "BAD_REQUEST")

        parent_dir, name = _split_path(norm)
        _validate_segment(name)
        parent_doc_id = None
        if parent_dir:
            parent_doc_id = await self._resolve_parent_document_id(agent_id, parent_dir)
            if parent_doc_id is None:
                raise AgentDocumentVfsError(
                    f"Parent directory not found: {parent_dir}", "NOT_FOUND"
                )

        # Check for existing file at same location
        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == name,
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        existing = result.one_or_none()

        now = _utcnow()
        stats = _get_document_stats(content)

        if existing:
            ad, doc = existing
            if doc.file_type == DOCUMENT_FOLDER_TYPE:
                raise AgentDocumentVfsError(
                    f"Cannot write to directory: {norm}", "BAD_REQUEST"
                )
            if not (ad.access_self & AgentAccess.WRITE):
                raise AgentDocumentVfsError(
                    f"Write access denied: {norm}", "FORBIDDEN"
                )
            # Update existing document
            doc.content = content
            doc.total_char_count = stats["total_char_count"]
            doc.total_line_count = stats["total_line_count"]
            if title:
                doc.title = title
            if metadata is not None:
                doc.metadata_ = metadata
            if editor_data is not None:
                doc.editor_data = editor_data
            doc.updated_at = now
            ad.updated_at = now
            self._db.add(doc)
            self._db.add(ad)
            await self._db.flush()
            return self._stats_from_row(ad, doc, norm).to_dict()

        # Create new document + binding
        display_title = title or name.rsplit(".", 1)[0]
        new_doc = Document(
            content=content,
            file_type=file_type,
            filename=name,
            parent_id=parent_doc_id,
            source=f"agent-document://{agent_id}/{name}",
            source_type="file",
            title=display_title,
            total_char_count=stats["total_char_count"],
            total_line_count=stats["total_line_count"],
            user_id=self._user_id,
            metadata_=metadata,
            editor_data=editor_data,
        )
        self._db.add(new_doc)
        await self._db.flush()

        new_ad = AgentDocument(
            agent_id=agent_id,
            document_id=new_doc.id,
            user_id=self._user_id,
            access_self=int(FULL_ACCESS),
            access_shared=0,
            access_public=0,
            policy_load="always",
            policy_load_position="before-first-user",
            policy_load_format="raw",
            policy_load_rule="always",
        )
        self._db.add(new_ad)
        await self._db.flush()

        return self._stats_from_row(new_ad, new_doc, norm).to_dict()

    # ── mkdir ────────────────────────────────────────────────────────

    async def mkdir(self, agent_id: str, path: str) -> dict[str, Any]:
        """Create a directory (folder) at *path*."""
        norm = _normalize_path(path)
        if norm == ".":
            raise AgentDocumentVfsError("Cannot mkdir root", "BAD_REQUEST")

        parent_dir, name = _split_path(norm)
        _validate_segment(name)
        parent_doc_id = None
        if parent_dir:
            parent_doc_id = await self._resolve_parent_document_id(agent_id, parent_dir)
            if parent_doc_id is None:
                raise AgentDocumentVfsError(
                    f"Parent directory not found: {parent_dir}", "NOT_FOUND"
                )

        # Check for conflict
        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == name,
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        if result.one_or_none():
            raise AgentDocumentVfsError(
                f"Path already exists: {norm}", "CONFLICT"
            )

        new_doc = Document(
            content="",
            file_type=DOCUMENT_FOLDER_TYPE,
            filename=name,
            parent_id=parent_doc_id,
            source=f"agent-document://{agent_id}/{name}",
            source_type="file",
            title=name,
            total_char_count=0,
            total_line_count=0,
            user_id=self._user_id,
        )
        self._db.add(new_doc)
        await self._db.flush()

        new_ad = AgentDocument(
            agent_id=agent_id,
            document_id=new_doc.id,
            user_id=self._user_id,
            access_self=int(FULL_ACCESS),
            access_shared=0,
            access_public=0,
            policy_load="disabled",
            policy_load_position="before-first-user",
            policy_load_format="raw",
            policy_load_rule="always",
        )
        self._db.add(new_ad)
        await self._db.flush()

        return self._stats_from_row(new_ad, new_doc, norm).to_dict()

    # ── rename / move ────────────────────────────────────────────────

    async def rename(
        self,
        agent_id: str,
        from_path: str,
        to_path: str,
    ) -> dict[str, Any]:
        """Move / rename a VFS entry."""
        norm_from = _normalize_path(from_path)
        norm_to = _normalize_path(to_path)

        if norm_from == "." or norm_to == ".":
            raise AgentDocumentVfsError("Cannot rename root", "BAD_REQUEST")
        if norm_from == norm_to:
            raise AgentDocumentVfsError("Source and destination are the same", "BAD_REQUEST")
        if norm_to.startswith(norm_from + "/"):
            raise AgentDocumentVfsError("Cannot move into itself", "BAD_REQUEST")

        # Resolve source
        src_parent_dir, src_name = _split_path(norm_from)
        src_parent_id = await self._resolve_parent_document_id(agent_id, src_parent_dir) if src_parent_dir else None

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == src_name,
                Document.parent_id == src_parent_id
                if src_parent_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        src_row = result.one_or_none()
        if not src_row:
            raise AgentDocumentVfsError(f"Source not found: {norm_from}", "NOT_FOUND")
        ad, doc = src_row

        # Resolve destination parent
        dst_parent_dir, dst_name = _split_path(norm_to)
        _validate_segment(dst_name)
        dst_parent_id = None
        if dst_parent_dir:
            dst_parent_id = await self._resolve_parent_document_id(agent_id, dst_parent_dir)
            if dst_parent_id is None:
                raise AgentDocumentVfsError(
                    f"Destination directory not found: {dst_parent_dir}", "NOT_FOUND"
                )

        # Apply move
        doc.filename = dst_name
        doc.parent_id = dst_parent_id
        doc.title = dst_name
        doc.source = f"agent-document://{agent_id}/{dst_name}"
        doc.updated_at = _utcnow()
        ad.updated_at = _utcnow()
        self._db.add(doc)
        self._db.add(ad)
        await self._db.flush()

        return self._stats_from_row(ad, doc, norm_to).to_dict()

    # ── copy ─────────────────────────────────────────────────────────

    async def copy(
        self,
        agent_id: str,
        from_path: str,
        to_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Copy a file. Directories are not recursively copied."""
        norm_from = _normalize_path(from_path)
        if norm_from == ".":
            raise AgentDocumentVfsError("Cannot copy root", "BAD_REQUEST")

        src_parent_dir, src_name = _split_path(norm_from)
        src_parent_id = await self._resolve_parent_document_id(agent_id, src_parent_dir) if src_parent_dir else None

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == src_name,
                Document.parent_id == src_parent_id
                if src_parent_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        src_row = result.one_or_none()
        if not src_row:
            raise AgentDocumentVfsError(f"Source not found: {norm_from}", "NOT_FOUND")
        _, src_doc = src_row

        if src_doc.file_type == DOCUMENT_FOLDER_TYPE:
            raise AgentDocumentVfsError("Cannot copy a directory", "BAD_REQUEST")

        # Determine destination
        if to_path:
            norm_to = _normalize_path(to_path)
        else:
            import time
            copy_name = f"copy-{int(time.time() * 1000)}-{src_doc.filename}"
            norm_to = f"{src_parent_dir}/{copy_name}" if src_parent_dir else copy_name

        return await self.write(
            agent_id,
            norm_to,
            src_doc.content or "",
            file_type=src_doc.file_type,
            title=src_doc.title,
            metadata=getattr(src_doc, "metadata_", None),
            editor_data=src_doc.editor_data,
        )

    # ── delete (soft) ────────────────────────────────────────────────

    async def delete(
        self,
        agent_id: str,
        path: str,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Soft-delete a file or directory (and its subtree)."""
        norm = _normalize_path(path)
        if norm == ".":
            raise AgentDocumentVfsError("Cannot delete root", "BAD_REQUEST")

        parent_dir, name = _split_path(norm)
        parent_doc_id = await self._resolve_parent_document_id(agent_id, parent_dir) if parent_dir else None

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                Document.filename == name,
                Document.parent_id == parent_doc_id
                if parent_doc_id
                else Document.parent_id.is_(None),
                AgentDocument.deleted_at.is_(None),
            )
            .order_by(asc(AgentDocument.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise AgentDocumentVfsError(f"Path not found: {norm}", "NOT_FOUND")
        ad, doc = row

        if not (ad.access_self & AgentAccess.DELETE):
            raise AgentDocumentVfsError(f"Delete access denied: {norm}", "FORBIDDEN")

        # Collect subtree if directory
        ids_to_delete = [ad.id]
        if doc.file_type == DOCUMENT_FOLDER_TYPE:
            subtree_ids = await self._collect_subtree_ids(agent_id, doc.id)
            ids_to_delete.extend(subtree_ids)

        now = _utcnow()
        await self._db.execute(
            update(AgentDocument)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.id.in_(ids_to_delete),
                AgentDocument.deleted_at.is_(None),
            )
            .values(
                deleted_at=now,
                deleted_by_user_id=self._user_id,
                delete_reason=reason,
                policy_load="disabled",
            )
        )
        await self._db.flush()

    async def _collect_subtree_ids(
        self, agent_id: str, root_document_id: str
    ) -> list[str]:
        """BFS to collect all descendant agent_document IDs."""
        collected: list[str] = []
        pending = [root_document_id]
        safety = 0
        while pending and safety < MAX_SUBTREE_CAP:
            safety += 1
            batch = pending[:]
            pending.clear()
            stmt = (
                select(AgentDocument.id, Document.id.label("doc_id"), Document.file_type)
                .join(Document, AgentDocument.document_id == Document.id)
                .where(
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.agent_id == agent_id,
                    Document.parent_id.in_(batch),
                    AgentDocument.deleted_at.is_(None),
                )
            )
            result = await self._db.execute(stmt)
            for ad_id, doc_id, ftype in result.all():
                collected.append(ad_id)
                if ftype == DOCUMENT_FOLDER_TYPE:
                    pending.append(doc_id)
        return collected

    # ── trash management ─────────────────────────────────────────────

    async def list_trash(self, agent_id: str) -> list[dict[str, Any]]:
        """List soft-deleted entries."""
        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.deleted_at.isnot(None),
            )
            .order_by(desc(AgentDocument.deleted_at))
        )
        result = await self._db.execute(stmt)
        entries: list[dict[str, Any]] = []
        for ad, doc in result.all():
            path = await self._get_full_path(agent_id, doc.id)
            entry = self._stats_from_row(ad, doc, path)
            entries.append(entry.to_dict())
        return entries

    async def restore_from_trash(self, agent_id: str, agent_document_id: str) -> None:
        """Restore a soft-deleted entry and its subtree."""
        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.id == agent_document_id,
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.deleted_at.isnot(None),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise AgentDocumentVfsError("Trash entry not found", "NOT_FOUND")

        ad, doc = row

        # Collect subtree IDs (including deleted)
        ids_to_restore = [ad.id]
        if doc.file_type == DOCUMENT_FOLDER_TYPE:
            ids_to_restore.extend(
                await self._collect_deleted_subtree_ids(agent_id, doc.id)
            )

        await self._db.execute(
            update(AgentDocument)
            .where(
                AgentDocument.user_id == self._user_id,
                AgentDocument.id.in_(ids_to_restore),
            )
            .values(
                deleted_at=None,
                deleted_by_user_id=None,
                deleted_by_agent_id=None,
                delete_reason=None,
                policy_load="always",
            )
        )
        await self._db.flush()

    async def delete_permanently(self, agent_id: str, agent_document_id: str) -> None:
        """Permanently delete a trashed entry (hard delete rows)."""
        from sqlalchemy import delete as sa_delete

        stmt = (
            select(AgentDocument, Document)
            .join(Document, AgentDocument.document_id == Document.id)
            .where(
                AgentDocument.id == agent_document_id,
                AgentDocument.user_id == self._user_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.deleted_at.isnot(None),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise AgentDocumentVfsError("Trash entry not found", "NOT_FOUND")

        ad, doc = row
        ids_to_delete = [ad.id]
        doc_ids_to_delete = [doc.id]

        if doc.file_type == DOCUMENT_FOLDER_TYPE:
            subtree = await self._collect_deleted_subtree_with_docs(agent_id, doc.id)
            for sid, did in subtree:
                ids_to_delete.append(sid)
                doc_ids_to_delete.append(did)

        # Delete agent_document bindings first, then documents
        await self._db.execute(
            sa_delete(AgentDocument).where(AgentDocument.id.in_(ids_to_delete))
        )
        await self._db.execute(
            sa_delete(Document).where(Document.id.in_(doc_ids_to_delete))
        )
        await self._db.flush()

    async def _collect_deleted_subtree_ids(
        self, agent_id: str, root_document_id: str
    ) -> list[str]:
        collected: list[str] = []
        pending = [root_document_id]
        safety = 0
        while pending and safety < MAX_SUBTREE_CAP:
            safety += 1
            batch = pending[:]
            pending.clear()
            stmt = (
                select(AgentDocument.id, Document.id.label("doc_id"), Document.file_type)
                .join(Document, AgentDocument.document_id == Document.id)
                .where(
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.agent_id == agent_id,
                    Document.parent_id.in_(batch),
                    AgentDocument.deleted_at.isnot(None),
                )
            )
            result = await self._db.execute(stmt)
            for ad_id, doc_id, ftype in result.all():
                collected.append(ad_id)
                if ftype == DOCUMENT_FOLDER_TYPE:
                    pending.append(doc_id)
        return collected

    async def _collect_deleted_subtree_with_docs(
        self, agent_id: str, root_document_id: str
    ) -> list[tuple[str, str]]:
        """BFS collecting (agent_document_id, document_id) pairs."""
        collected: list[tuple[str, str]] = []
        pending = [root_document_id]
        safety = 0
        while pending and safety < MAX_SUBTREE_CAP:
            safety += 1
            batch = pending[:]
            pending.clear()
            stmt = (
                select(AgentDocument.id, AgentDocument.document_id, Document.file_type)
                .join(Document, AgentDocument.document_id == Document.id)
                .where(
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.agent_id == agent_id,
                    Document.parent_id.in_(batch),
                    AgentDocument.deleted_at.isnot(None),
                )
            )
            result = await self._db.execute(stmt)
            for ad_id, doc_id, ftype in result.all():
                collected.append((ad_id, doc_id))
                if ftype == DOCUMENT_FOLDER_TYPE:
                    pending.append(doc_id)
        return collected


# ── module-level helpers ────────────────────────────────────────────

def _get_document_stats(content: str) -> dict[str, int]:
    if not content:
        return {"total_char_count": 0, "total_line_count": 0}
    return {
        "total_char_count": len(content),
        "total_line_count": content.count("\n") + 1,
    }

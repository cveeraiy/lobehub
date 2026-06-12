import pytest

from app.models.agent_ops import AgentDocument
from app.models.file import Document
from app.models.task import TaskDocument
from app.models.topic_ext import TopicDocument
from app.tools.agent_documents_tool import run_agent_documents_api

pytestmark = pytest.mark.asyncio


class FakeResult:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def all(self):
        return self.rows

    def one_or_none(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.agent_documents: dict[str, AgentDocument] = {}
        self.topic_documents: list[TopicDocument] = []
        self.task_documents: list[TaskDocument] = []

    def add(self, obj):
        if isinstance(obj, Document):
            self.documents[obj.id] = obj
        elif isinstance(obj, AgentDocument):
            self.agent_documents[obj.id] = obj
        elif isinstance(obj, TopicDocument):
            self.topic_documents.append(obj)
        elif isinstance(obj, TaskDocument):
            self.task_documents.append(obj)

    async def flush(self):
        return None

    async def refresh(self, obj):
        return None

    async def execute(self, statement):
        if hasattr(statement, "column_descriptions"):
            values = set(statement.compile().params.values())
            entities = [item.get("entity") for item in statement.column_descriptions]

            if entities[:2] == [AgentDocument, Document]:
                rows = [
                    (link, self.documents[link.document_id])
                    for link in self.agent_documents.values()
                    if link.agent_id in values
                    and link.user_id in values
                    and link.deleted_at is None
                    and link.document_id in self.documents
                ]
                matching_by_id = [row for row in rows if row[0].id in values]
                if matching_by_id:
                    return FakeResult(matching_by_id[0], matching_by_id)

                topic_ids = {link.topic_id for link in self.topic_documents if link.topic_id in values}
                if topic_ids:
                    topic_doc_ids = {
                        link.document_id for link in self.topic_documents if link.topic_id in topic_ids
                    }
                    rows = [row for row in rows if row[1].id in topic_doc_ids]
                return FakeResult(rows=rows)

            if entities[:1] == [TaskDocument]:
                return FakeResult(
                    next(
                        (
                            item
                            for item in self.task_documents
                            if item.task_id in values and item.document_id in values and item.user_id in values
                        ),
                        None,
                    )
                )

        table_name = getattr(getattr(statement, "table", None), "name", "")
        values = statement.compile().params
        match_values = set(values.values())

        if table_name == "agent_documents":
            for link in self.agent_documents.values():
                if link.id in match_values:
                    if "deleted_at" in values:
                        link.deleted_at = values["deleted_at"]
                    if "policy_load" in values:
                        link.policy_load = values["policy_load"]
                    if "policy" in values:
                        link.policy = values["policy"]
                    if "policy_load_rule" in values:
                        link.policy_load_rule = values["policy_load_rule"]

        if table_name == "documents":
            for doc in self.documents.values():
                if doc.id in match_values:
                    if "content" in values:
                        doc.content = values["content"]
                    if "title" in values:
                        doc.title = values["title"]
                    if "editor_data" in values:
                        doc.editor_data = values["editor_data"]

        return FakeResult()


async def test_create_document_uses_agent_document_id_and_pins_task():
    session = FakeSession()

    result = await run_agent_documents_api(
        "createDocument",
        {
            "agentId": "agent-1",
            "content": "# Extracted\n\nBody",
            "taskId": "task-1",
            "title": "Fallback",
            "topicId": "topic-1",
            "target": "currentTopic",
        },
        session=session,
        user_id="user-1",
    )

    assert result["success"] is True
    agent_doc_id = result["content"].split("(")[-1].rstrip(").")
    assert agent_doc_id in session.agent_documents
    assert result["state"]["documentId"] == session.agent_documents[agent_doc_id].document_id
    assert session.documents[result["state"]["documentId"]].title == "Extracted"
    assert len(session.topic_documents) == 1
    assert len(session.task_documents) == 1


async def test_read_and_list_documents_return_runtime_shapes():
    session = FakeSession()
    created = await run_agent_documents_api(
        "createDocument",
        {"agentId": "agent-1", "content": "Body", "title": "Doc"},
        session=session,
        user_id="user-1",
    )
    agent_doc_id = created["content"].split("(")[-1].rstrip(").")

    read = await run_agent_documents_api(
        "readDocument",
        {"agentId": "agent-1", "format": "markdown", "id": agent_doc_id},
        session=session,
        user_id="user-1",
    )
    listed = await run_agent_documents_api(
        "listDocuments",
        {"agentId": "agent-1"},
        session=session,
        user_id="user-1",
    )

    assert read == {
        "content": "Body",
        "state": {"content": "Body", "id": agent_doc_id, "title": "Doc", "xml": "Body"},
        "success": True,
    }
    assert listed["success"] is True
    assert listed["state"]["documents"][0]["id"] == agent_doc_id
    assert listed["state"]["documents"][0]["documentId"] == created["state"]["documentId"]


async def test_page_scope_blocks_current_page_writes():
    session = FakeSession()
    created = await run_agent_documents_api(
        "createDocument",
        {"agentId": "agent-1", "content": "Body", "title": "Doc"},
        session=session,
        user_id="user-1",
    )
    agent_doc_id = created["content"].split("(")[-1].rstrip(").")

    blocked = await run_agent_documents_api(
        "replaceDocumentContent",
        {
            "agentId": "agent-1",
            "content": "Updated",
            "currentDocumentId": created["state"]["documentId"],
            "id": agent_doc_id,
            "scope": "page",
        },
        session=session,
        user_id="user-1",
    )

    assert blocked["success"] is False
    assert blocked["error"]["code"] == "CURRENT_PAGE_DOCUMENT_WRITE_FORBIDDEN"

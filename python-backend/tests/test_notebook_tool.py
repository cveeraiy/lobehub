import json
from typing import Any

import pytest

from app.models.file import Document
from app.models.task import TaskDocument
from app.models.topic_ext import TopicDocument
from app.tools.notebook_tool import run_notebook_api

pytestmark = pytest.mark.asyncio


class FakeResult:
    def __init__(self, value: Any = None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.topic_documents: list[TopicDocument] = []
        self.task_documents: list[TaskDocument] = []

    def add(self, obj: Any):
        if isinstance(obj, Document):
            self.documents[obj.id] = obj
        elif isinstance(obj, TopicDocument):
            self.topic_documents.append(obj)
        elif isinstance(obj, TaskDocument):
            self.task_documents.append(obj)

    async def flush(self):
        return None

    async def refresh(self, obj: Any):
        return None

    async def execute(self, statement: Any):
        if hasattr(statement, "column_descriptions"):
            entity = statement.column_descriptions[0].get("entity")
            values = set(statement.compile().params.values())

            if entity is Document:
                return FakeResult(next((doc for doc in self.documents.values() if doc.id in values), None))

            if entity is TopicDocument:
                return FakeResult(
                    next(
                        (
                            link
                            for link in self.topic_documents
                            if link.topic_id in values and link.document_id in values and link.user_id in values
                        ),
                        None,
                    )
                )

            if entity is TaskDocument:
                return FakeResult(
                    next(
                        (
                            link
                            for link in self.task_documents
                            if link.task_id in values and link.document_id in values and link.user_id in values
                        ),
                        None,
                    )
                )

        table_name = getattr(getattr(statement, "table", None), "name", "")
        values = set(statement.compile().params.values())

        if table_name == "documents":
            for doc_id in list(self.documents):
                if doc_id in values:
                    del self.documents[doc_id]
        elif table_name == "topic_documents":
            self.topic_documents = [link for link in self.topic_documents if link.document_id not in values]
        elif table_name == "task_documents":
            self.task_documents = [link for link in self.task_documents if link.document_id not in values]

        return FakeResult()


async def test_create_document_matches_ts_runtime_shape():
    session = FakeSession()

    result = await run_notebook_api(
        "createDocument",
        {
            "content": "hello notebook",
            "taskId": "task-1",
            "title": "Plan",
            "topicId": "topic-1",
            "type": "markdown",
        },
        session=session,
        user_id="user-1",
    )

    assert result["success"] is True
    assert result["content"] == (
        '📄 Created document: "Plan"\n\nYou can view and edit this document in the Portal sidebar.'
    )
    document = result["state"]["document"]
    assert document["title"] == "Plan"
    assert document["content"] == "hello notebook"
    assert document["sourceType"] == "ai"
    assert document["wordCount"] == 2

    stored = session.documents[document["id"]]
    assert stored.source == "notebook:topic-1"
    assert stored.total_line_count == 1
    assert len(session.topic_documents) == 1
    assert len(session.task_documents) == 1


async def test_create_document_requires_content_and_topic_context():
    session = FakeSession()

    missing_content = await run_notebook_api(
        "createDocument",
        {"content": "", "title": "Empty", "topicId": "topic-1"},
        session=session,
        user_id="user-1",
    )
    missing_topic = await run_notebook_api(
        "createDocument",
        {"content": "body", "title": "No topic"},
        session=session,
        user_id="user-1",
    )

    assert missing_content["success"] is False
    assert missing_content["error"]["type"] == "MissingContentError"
    assert missing_topic["success"] is False
    assert missing_topic["error"]["type"] == "MissingTopicContextError"


async def test_update_get_and_delete_document_match_ts_runtime_shape():
    session = FakeSession()
    created = await run_notebook_api(
        "createDocument",
        {"content": "alpha", "title": "Draft", "topicId": "topic-1"},
        session=session,
        user_id="user-1",
    )
    document_id = created["state"]["document"]["id"]

    updated = await run_notebook_api(
        "updateDocument",
        {"append": True, "content": "beta", "id": document_id, "title": "Published"},
        session=session,
        user_id="user-1",
    )
    fetched = await run_notebook_api(
        "getDocument",
        {"id": document_id},
        session=session,
        user_id="user-1",
    )
    deleted = await run_notebook_api(
        "deleteDocument",
        {"id": document_id},
        session=session,
        user_id="user-1",
    )
    missing = await run_notebook_api(
        "getDocument",
        {"id": document_id},
        session=session,
        user_id="user-1",
    )

    assert updated["success"] is True
    assert updated["content"] == '📝 Appended to document: "Published"'
    assert updated["state"]["document"]["content"] == "alpha\n\nbeta"
    assert updated["state"]["document"]["wordCount"] == len("alpha\n\nbeta")
    assert fetched["content"] == '📄 Document: "Published"\n\nalpha\n\nbeta'
    assert deleted == {
        "content": '🗑️ Deleted document: "Published"',
        "state": {"deletedId": document_id},
        "success": True,
    }
    assert missing["success"] is False
    assert missing["error"]["type"] == "DocumentNotFoundError"
    assert session.documents == {}
    assert session.topic_documents == []


async def test_context_dispatcher_result_can_be_json_encoded():
    session = FakeSession()
    result = await run_notebook_api(
        "unknown",
        {},
        session=session,
        user_id="user-1",
    )

    encoded = json.loads(json.dumps(result))
    assert encoded["success"] is False
    assert encoded["error"]["type"] == "UnknownApiError"

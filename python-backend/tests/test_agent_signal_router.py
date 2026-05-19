import pytest

from app.routers import agent_signal


class DummyOrchestrator:
    def __init__(self):
        self.signals = []

    async def emit(self, signal):
        self.signals.append(signal)
        return []


@pytest.mark.asyncio
async def test_emit_signal_accepts_client_source_event(monkeypatch):
    orchestrator = DummyOrchestrator()
    monkeypatch.setattr(agent_signal, "get_orchestrator", lambda: orchestrator)

    response = await agent_signal.emit_signal(
        agent_signal.EmitSignalRequest(
            payload={"topicId": "topic-1"},
            user_id="spoofed-user",
            scopeKey="topic:topic-1",
            sourceId="client.gateway.stream_start:1",
            sourceType="client.gateway.stream_start",
            timestamp=1,
        ),
        user_id="auth-user",
    )

    assert response.success is True
    assert len(orchestrator.signals) == 1
    signal = orchestrator.signals[0]
    assert signal.source == "client.gateway.stream_start"
    assert signal.type == "client.gateway.stream_start"
    assert signal.user_id == "auth-user"
    assert signal.scope == "topic:topic-1"
    assert signal.dedup_key == "client.gateway.stream_start:1"

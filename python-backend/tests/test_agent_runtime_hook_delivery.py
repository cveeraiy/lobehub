import pytest

from app.services.agent_runtime_hooks.dispatcher import HookDispatcher


@pytest.mark.asyncio
async def test_qstash_hook_delivery_uses_temporal(monkeypatch):
    calls = []

    async def fake_temporal_delivery(url, payload, *, hook_id=None):
        calls.append({"hook_id": hook_id, "payload": payload, "url": url})
        return {"success": True, "workflowId": "wf_1"}

    monkeypatch.setattr(
        "app.services.workflows.temporal_backend.start_temporal_webhook_delivery",
        fake_temporal_delivery,
    )

    dispatcher = HookDispatcher()
    await dispatcher.dispatch(
        "op_1",
        "afterStep",
        {"finalState": {"large": True}, "operationId": "op_1", "step": 1},
        serialized_hooks=[
            {
                "id": "hook_1",
                "type": "afterStep",
                "webhook": {
                    "delivery": "qstash",
                    "url": "https://example.test/hook",
                },
            }
        ],
    )

    assert calls == [
        {
            "hook_id": "hook_1",
            "payload": {
                "hookId": "hook_1",
                "hookType": "afterStep",
                "operationId": "op_1",
                "step": 1,
            },
            "url": "https://example.test/hook",
        }
    ]

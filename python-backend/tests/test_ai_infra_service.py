from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.ai_infra_service import service


@pytest.mark.asyncio
async def test_update_provider_config_accepts_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    monkeypatch.setattr(service, "get_provider_detail", AsyncMock(return_value=None))

    await service.update_provider_config(session, "user-id", "anthropic")

    session.execute.assert_awaited_once()

"""Tests for app.dependencies — service token auth bridge.

Verifies that the dual auth mechanism (service token vs OIDC JWT)
works correctly in ``get_current_user_id`` and ``_validate_service_token``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.dependencies import _validate_service_token


# ── _validate_service_token ──────────────────────────────────────────


class TestValidateServiceToken:
    """Unit tests for the internal service token validator."""

    def _make_request(
        self,
        service_token: str | None = None,
        user_id: str | None = None,
    ) -> MagicMock:
        """Build a mock Request with the given headers."""
        headers: dict[str, str] = {}
        if service_token is not None:
            headers["x-service-token"] = service_token
        if user_id is not None:
            headers["x-internal-user-id"] = user_id

        request = MagicMock()
        request.headers = headers
        return request

    @patch("app.dependencies.settings")
    def test_returns_none_when_no_service_token_header(self, mock_settings: MagicMock) -> None:
        """No X-Service-Token header → returns None (fall through to JWT)."""
        mock_settings.python_backend_service_token = "secret"
        request = self._make_request()
        assert _validate_service_token(request) is None

    @patch("app.dependencies.settings")
    def test_returns_none_when_service_token_not_configured(self, mock_settings: MagicMock) -> None:
        """Service token sent but server has no configured token → returns None."""
        mock_settings.python_backend_service_token = None
        request = self._make_request(service_token="some-token", user_id="user-1")
        assert _validate_service_token(request) is None

    @patch("app.dependencies.settings")
    def test_raises_401_on_invalid_token(self, mock_settings: MagicMock) -> None:
        """Service token doesn't match → 401."""
        mock_settings.python_backend_service_token = "correct-secret"
        request = self._make_request(service_token="wrong-secret", user_id="user-1")
        with pytest.raises(HTTPException) as exc_info:
            _validate_service_token(request)
        assert exc_info.value.status_code == 401
        assert "Invalid service token" in exc_info.value.detail

    @patch("app.dependencies.settings")
    def test_raises_400_when_user_id_missing(self, mock_settings: MagicMock) -> None:
        """Valid token but no X-Internal-User-Id → 400."""
        mock_settings.python_backend_service_token = "correct-secret"
        request = self._make_request(service_token="correct-secret")
        with pytest.raises(HTTPException) as exc_info:
            _validate_service_token(request)
        assert exc_info.value.status_code == 400
        assert "X-Internal-User-Id" in exc_info.value.detail

    @patch("app.dependencies.settings")
    def test_returns_user_id_on_valid_token(self, mock_settings: MagicMock) -> None:
        """Valid token + user ID → returns user ID string."""
        mock_settings.python_backend_service_token = "correct-secret"
        request = self._make_request(service_token="correct-secret", user_id="user-42")
        result = _validate_service_token(request)
        assert result == "user-42"

    @patch("app.dependencies.settings")
    def test_timing_safe_comparison(self, mock_settings: MagicMock) -> None:
        """Ensure comparison uses constant-time hmac.compare_digest (no short-circuit)."""
        mock_settings.python_backend_service_token = "a" * 32
        # A token that shares a long prefix should still fail
        request = self._make_request(service_token="a" * 31 + "b", user_id="user-1")
        with pytest.raises(HTTPException) as exc_info:
            _validate_service_token(request)
        assert exc_info.value.status_code == 401


# ── get_current_user_id integration ──────────────────────────────────


class TestGetCurrentUserIdServiceToken:
    """Tests that get_current_user_id prefers service token auth."""

    @pytest.mark.asyncio
    @patch("app.dependencies._ensure_user_exists", new_callable=AsyncMock)
    @patch("app.dependencies._validate_service_token")
    async def test_uses_service_token_when_present(
        self,
        mock_validate: MagicMock,
        mock_ensure: AsyncMock,
    ) -> None:
        """When service token is valid, should NOT call OIDC JWT auth."""
        from app.dependencies import get_current_user_id

        mock_validate.return_value = "user-proxied"
        mock_ensure.return_value = "user-proxied"

        mock_request = MagicMock()
        mock_session = AsyncMock()

        result = await get_current_user_id(request=mock_request, session=mock_session)

        assert result == "user-proxied"
        mock_validate.assert_called_once_with(mock_request)
        mock_ensure.assert_called_once_with(mock_session, "user-proxied")

    @pytest.mark.asyncio
    @patch("app.dependencies._extract_bearer", new_callable=AsyncMock)
    @patch("app.dependencies.get_or_create_user", new_callable=AsyncMock)
    @patch("app.dependencies.get_current_user", new_callable=AsyncMock)
    @patch("app.dependencies._validate_service_token")
    async def test_falls_back_to_jwt_when_no_service_token(
        self,
        mock_validate: MagicMock,
        mock_get_user: AsyncMock,
        mock_get_or_create: AsyncMock,
        mock_extract: AsyncMock,
    ) -> None:
        """When service token returns None, should fall back to JWT auth."""
        from app.dependencies import get_current_user_id

        mock_validate.return_value = None

        mock_token = MagicMock()
        mock_token.sub = "jwt-user-1"
        mock_get_user.return_value = mock_token
        mock_extract.return_value = "bearer-creds"

        mock_user = MagicMock()
        mock_user.id = "jwt-user-1"
        mock_get_or_create.return_value = mock_user

        mock_request = MagicMock()
        mock_session = AsyncMock()

        result = await get_current_user_id(request=mock_request, session=mock_session)

        assert result == "jwt-user-1"
        mock_validate.assert_called_once_with(mock_request)
        mock_extract.assert_called_once_with(mock_request)

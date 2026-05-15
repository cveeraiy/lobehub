"""AI Infrastructure router — Provider & Model CRUD + Runtime.

Mirrors the TS ``aiProviderRouter`` and ``aiModelRouter`` TRPC routers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import ai_infra_service as svc
from app.services.key_vault import KeyVaultService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-infra", tags=["AI Infrastructure"])


# ── Helpers ──────────────────────────────────────────────────────────

def _get_vault() -> KeyVaultService | None:
    """Return a KeyVaultService if KEY_VAULTS_SECRET is configured."""
    try:
        return KeyVaultService.from_env()
    except RuntimeError:
        return None


# ── Pydantic schemas ────────────────────────────────────────────────

class CreateProviderBody(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    key_vaults: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    check_model: Optional[str] = None
    fetch_on_client: Optional[bool] = None


class UpdateProviderBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None


class UpdateProviderConfigBody(BaseModel):
    key_vaults: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    check_model: Optional[str] = None
    fetch_on_client: Optional[bool] = None


class ToggleEnabledBody(BaseModel):
    enabled: bool


class ProviderSortItem(BaseModel):
    id: str
    sort: int


class UpdateProviderOrderBody(BaseModel):
    sort_map: list[ProviderSortItem]


class CreateModelBody(BaseModel):
    id: str
    provider_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    type: str = "chat"
    enabled: bool = True
    abilities: Optional[dict[str, Any]] = None
    parameters: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    pricing: Optional[dict[str, Any]] = None
    context_window_tokens: Optional[int] = None


class UpdateModelBody(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    abilities: Optional[dict[str, Any]] = None
    parameters: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    pricing: Optional[dict[str, Any]] = None
    context_window_tokens: Optional[int] = None


class ToggleModelBody(BaseModel):
    id: str
    provider_id: str
    enabled: bool
    type: Optional[str] = None


class BatchToggleModelsBody(BaseModel):
    id: str  # provider_id
    models: list[str]
    enabled: bool


class ModelSortItem(BaseModel):
    id: str
    sort: int
    type: Optional[str] = None


class UpdateModelOrderBody(BaseModel):
    provider_id: str
    sort_map: list[ModelSortItem]


# =====================================================================
#  Provider endpoints
# =====================================================================

@router.get("/providers")
async def list_providers(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await svc.get_provider_list(session, user_id)


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    vault = _get_vault()
    detail = await svc.get_provider_detail(session, user_id, provider_id, vault)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return detail


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: CreateProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    vault = _get_vault()
    try:
        provider = await svc.create_provider(
            session, user_id,
            id=body.id,
            name=body.name,
            description=body.description,
            logo=body.logo,
            key_vaults=body.key_vaults,
            settings=body.settings,
            config=body.config,
            check_model=body.check_model,
            fetch_on_client=body.fetch_on_client,
            vault=vault,
        )
        return {"id": provider.id}
    except Exception as exc:
        # Unique-constraint violation
        if "duplicate key" in str(exc).lower() or "23505" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'Provider "{body.id}" already exists',
            ) from exc
        raise


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    body: UpdateProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.update_provider(
        session, user_id, provider_id,
        name=body.name,
        description=body.description,
        logo=body.logo,
    )
    return {"ok": True}


@router.put("/providers/{provider_id}/config")
async def update_provider_config(
    provider_id: str,
    body: UpdateProviderConfigBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    vault = _get_vault()
    await svc.update_provider_config(
        session, user_id, provider_id,
        key_vaults=body.key_vaults,
        config=body.config,
        check_model=body.check_model,
        fetch_on_client=body.fetch_on_client,
        vault=vault,
    )
    return {"ok": True}


@router.put("/providers/{provider_id}/enabled")
async def toggle_provider(
    provider_id: str,
    body: ToggleEnabledBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.toggle_provider_enabled(session, user_id, provider_id, body.enabled)
    return {"ok": True}


@router.put("/providers/order")
async def update_provider_order(
    body: UpdateProviderOrderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.update_provider_order(
        session, user_id,
        [{"id": i.id, "sort": i.sort} for i in body.sort_map],
    )
    return {"ok": True}


@router.delete("/providers/{provider_id}")
async def remove_provider(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.delete_provider(session, user_id, provider_id)
    return {"ok": True}


# =====================================================================
#  Model endpoints
# =====================================================================

@router.get("/providers/{provider_id}/models")
async def list_models(
    provider_id: str,
    enabled: Optional[bool] = None,
    type: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await svc.get_provider_model_list(
        session, user_id, provider_id,
        enabled=enabled,
        model_type=type,
        limit=limit,
        offset=offset,
    )


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    model = await svc.get_model_by_id(session, user_id, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model(
    body: CreateModelBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    model = await svc.create_model(
        session, user_id,
        id=body.id,
        provider_id=body.provider_id,
        display_name=body.display_name,
        description=body.description,
        type=body.type,
        enabled=body.enabled,
        abilities=body.abilities,
        parameters=body.parameters,
        config=body.config,
        settings=body.settings,
        pricing=body.pricing,
        context_window_tokens=body.context_window_tokens,
    )
    return {"id": model.id}


@router.put("/models/{model_id}/provider/{provider_id}")
async def update_model(
    model_id: str,
    provider_id: str,
    body: UpdateModelBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    await svc.update_model(session, user_id, model_id, provider_id, **values)
    return {"ok": True}


@router.put("/models/toggle")
async def toggle_model(
    body: ToggleModelBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.toggle_model_enabled(
        session, user_id, body.id, body.provider_id, body.enabled, body.type
    )
    return {"ok": True}


@router.put("/models/batch-toggle")
async def batch_toggle_models(
    body: BatchToggleModelsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.batch_toggle_models(session, user_id, body.id, body.models, body.enabled)
    return {"ok": True}


@router.put("/models/order")
async def update_model_order(
    body: UpdateModelOrderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.update_model_order(
        session, user_id, body.provider_id,
        [i.model_dump() for i in body.sort_map],
    )
    return {"ok": True}


@router.delete("/models/{model_id}/provider/{provider_id}")
async def remove_model(
    model_id: str,
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.delete_model(session, user_id, model_id, provider_id)
    return {"ok": True}


@router.delete("/providers/{provider_id}/models")
async def clear_provider_models(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.clear_models_by_provider(session, user_id, provider_id)
    return {"ok": True}


@router.delete("/providers/{provider_id}/models/remote")
async def clear_remote_models(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.clear_remote_models(session, user_id, provider_id)
    return {"ok": True}


# =====================================================================
#  Runtime
# =====================================================================

@router.get("/runtime")
async def get_runtime_state(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    vault = _get_vault()
    return await svc.get_runtime_state(session, user_id, vault)

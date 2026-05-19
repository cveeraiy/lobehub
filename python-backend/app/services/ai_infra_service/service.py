"""AI Infrastructure service — Provider & Model CRUD with merge logic.

Mirrors the TS ``AiProviderModel``, ``AiModelModel``, and ``AiInfraRepos``
classes.  All methods are async and operate within a supplied
``AsyncSession``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, asc, delete, desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_infra import AiModel, AiProvider
from app.services.key_vault import KeyVaultService
from app.services.model_catalog import (
    BUILTIN_PROVIDERS,
    get_builtin_provider,
    get_builtin_models,
    get_provider_sort_key,
    is_builtin_provider,
    get_provider_source,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _model_abilities(provider_id: str, model_id: str, abilities: Optional[dict[str, Any]]) -> dict[str, Any]:
    values = dict(abilities or {})
    if provider_id == "bedrock":
        if (
            model_id.startswith("anthropic.")
            or model_id.startswith("global.anthropic.")
            or model_id.startswith("us.anthropic.")
        ):
            values.setdefault("functionCall", True)
            values.setdefault("vision", True)
    return values


# ─────────────────────────────────────────────────────────────────────
#  Provider CRUD
# ─────────────────────────────────────────────────────────────────────

async def create_provider(
    session: AsyncSession,
    user_id: str,
    *,
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    logo: Optional[str] = None,
    key_vaults: Optional[dict[str, Any]] = None,
    settings: Optional[dict[str, Any]] = None,
    config: Optional[dict[str, Any]] = None,
    check_model: Optional[str] = None,
    fetch_on_client: Optional[bool] = None,
    vault: Optional[KeyVaultService] = None,
) -> AiProvider:
    """Create (or conflict-raise) an AI provider for the given user."""
    encrypted_kv: Optional[str] = None
    if key_vaults and vault:
        encrypted_kv = vault.encrypt_json(key_vaults)
    elif key_vaults:
        encrypted_kv = json.dumps(key_vaults)

    provider = AiProvider(
        id=id,
        user_id=user_id,
        name=name,
        description=description,
        logo=logo,
        enabled=True,
        source=get_provider_source(id),
        key_vaults=encrypted_kv,
        settings=settings,
        config=config,
        check_model=check_model,
        fetch_on_client=fetch_on_client,
    )
    session.add(provider)
    await session.flush()
    return provider


async def get_provider_list(
    session: AsyncSession,
    user_id: str,
) -> list[dict[str, Any]]:
    """Return merged builtin + user provider list (ordered)."""
    stmt = (
        select(
            AiProvider.id,
            AiProvider.name,
            AiProvider.description,
            AiProvider.logo,
            AiProvider.enabled,
            AiProvider.sort,
            AiProvider.source,
        )
        .where(AiProvider.user_id == user_id)
        .order_by(asc(AiProvider.sort), desc(AiProvider.updated_at))
    )
    rows = (await session.execute(stmt)).all()
    user_map = {r.id: dict(r._mapping) for r in rows}

    # Build merged list: builtins first, then custom-only providers
    merged: list[dict[str, Any]] = []
    seen = set()
    for bp in BUILTIN_PROVIDERS:
        if bp.id in user_map:
            entry = _provider_list_entry(user_map[bp.id], bp)
        else:
            entry = {
                "id": bp.id,
                "name": bp.name,
                "description": bp.description,
                "logo": None,
                "enabled": False,
                "sort": bp.sort,
                "source": "builtin",
            }
        merged.append(entry)
        seen.add(bp.id)

    # Append custom providers not in the builtin list
    for pid, entry in user_map.items():
        if pid not in seen:
            merged.append(entry)

    return merged


def _provider_list_entry(
    row: dict[str, Any],
    builtin: Any,
) -> dict[str, Any]:
    return {
        **row,
        "name": row.get("name") or builtin.name,
        "description": row.get("description") or builtin.description,
        "logo": row.get("logo"),
        "sort": row.get("sort") if row.get("sort") is not None else builtin.sort,
        "source": row.get("source") or "builtin",
    }


async def get_provider_detail(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    vault: Optional[KeyVaultService] = None,
) -> dict[str, Any] | None:
    """Return full detail of a provider, with decrypted key vaults."""
    stmt = (
        select(AiProvider)
        .where(and_(AiProvider.id == provider_id, AiProvider.user_id == user_id))
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        # Auto-init builtin provider if not yet in DB
        if is_builtin_provider(provider_id):
            provider = AiProvider(id=provider_id, user_id=user_id, source="builtin")
            session.add(provider)
            await session.flush()
            return _provider_to_detail(provider, vault)
        return None

    return _provider_to_detail(row, vault)


def _provider_to_detail(
    p: AiProvider,
    vault: Optional[KeyVaultService] = None,
) -> dict[str, Any]:
    builtin = get_builtin_provider(p.id)
    kv: dict[str, Any] = {}
    if p.key_vaults and vault:
        kv = vault.decrypt_json(p.key_vaults)
    elif p.key_vaults:
        try:
            kv = json.loads(p.key_vaults)
        except Exception:
            pass
    return {
        "id": p.id,
        "name": p.name or (builtin.name if builtin else None),
        "description": p.description or (builtin.description if builtin else None),
        "logo": p.logo,
        "enabled": p.enabled,
        "sort": p.sort if p.sort is not None else (builtin.sort if builtin else None),
        "source": p.source or get_provider_source(p.id),
        "key_vaults": kv,
        "settings": p.settings or None,
        "config": p.config or None,
        "check_model": p.check_model,
        "fetch_on_client": p.fetch_on_client,
    }


async def update_provider(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    logo: Optional[str] = None,
) -> None:
    """Update basic provider fields."""
    values: dict[str, Any] = {"updated_at": _now()}
    if name is not None:
        values["name"] = name
    if description is not None:
        values["description"] = description
    if logo is not None:
        values["logo"] = logo
    stmt = (
        update(AiProvider)
        .where(and_(AiProvider.id == provider_id, AiProvider.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)


async def update_provider_config(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    *,
    key_vaults: Optional[dict[str, Any]] = None,
    config: Optional[dict[str, Any]] = None,
    check_model: Optional[str] = None,
    fetch_on_client: Optional[bool] = None,
    vault: Optional[KeyVaultService] = None,
) -> None:
    """Upsert provider config (key vaults are merge-updated)."""
    # Merge key vaults with existing to preserve fields not in the update
    merged_kv = key_vaults or {}
    existing = await get_provider_detail(session, user_id, provider_id, vault)
    if existing and existing.get("key_vaults"):
        merged_kv = {**existing["key_vaults"], **merged_kv}

    encrypted_kv: Optional[str] = None
    if merged_kv and vault:
        encrypted_kv = vault.encrypt_json(merged_kv)
    elif merged_kv:
        encrypted_kv = json.dumps(merged_kv)

    common = {
        "key_vaults": encrypted_kv,
        "config": config,
        "check_model": check_model,
        "fetch_on_client": fetch_on_client,
    }
    # Remove None values so we only set fields that were provided
    common = {k: v for k, v in common.items() if v is not None}

    stmt = pg_insert(AiProvider).values(
        id=provider_id,
        user_id=user_id,
        source=get_provider_source(provider_id),
        **common,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AiProvider.id, AiProvider.user_id],
        set_=common,
    )
    await session.execute(stmt)


async def toggle_provider_enabled(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    enabled: bool,
) -> None:
    stmt = pg_insert(AiProvider).values(
        id=provider_id,
        user_id=user_id,
        enabled=enabled,
        source=get_provider_source(provider_id),
        updated_at=_now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AiProvider.id, AiProvider.user_id],
        set_={"enabled": enabled, "updated_at": _now()},
    )
    await session.execute(stmt)


async def update_provider_order(
    session: AsyncSession,
    user_id: str,
    sort_map: list[dict[str, Any]],
) -> None:
    for item in sort_map:
        stmt = pg_insert(AiProvider).values(
            id=item["id"],
            user_id=user_id,
            enabled=True,
            sort=item["sort"],
            source=get_provider_source(item["id"]),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AiProvider.id, AiProvider.user_id],
            set_={"sort": item["sort"], "updated_at": _now()},
        )
        await session.execute(stmt)


async def delete_provider(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
) -> None:
    """Delete a provider and all its models."""
    await session.execute(
        delete(AiModel).where(
            and_(AiModel.provider_id == provider_id, AiModel.user_id == user_id)
        )
    )
    await session.execute(
        delete(AiProvider).where(
            and_(AiProvider.id == provider_id, AiProvider.user_id == user_id)
        )
    )


# ─────────────────────────────────────────────────────────────────────
#  Model CRUD
# ─────────────────────────────────────────────────────────────────────

async def create_model(
    session: AsyncSession,
    user_id: str,
    *,
    id: str,
    provider_id: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    type: str = "chat",
    enabled: bool = True,
    abilities: Optional[dict[str, Any]] = None,
    parameters: Optional[dict[str, Any]] = None,
    config: Optional[dict[str, Any]] = None,
    settings: Optional[dict[str, Any]] = None,
    pricing: Optional[dict[str, Any]] = None,
    context_window_tokens: Optional[int] = None,
) -> AiModel:
    model = AiModel(
        id=id,
        provider_id=provider_id,
        user_id=user_id,
        display_name=display_name,
        description=description,
        type=type,
        enabled=enabled,
        source="custom",
        abilities=abilities,
        parameters=parameters,
        config=config,
        settings=settings,
        pricing=pricing,
        context_window_tokens=context_window_tokens,
    )
    session.add(model)
    await session.flush()
    return model


async def get_model_by_id(
    session: AsyncSession,
    user_id: str,
    model_id: str,
) -> AiModel | None:
    stmt = select(AiModel).where(
        and_(AiModel.id == model_id, AiModel.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_provider_model_list(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    *,
    enabled: Optional[bool] = None,
    model_type: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return merged builtin + user models for a provider."""
    # Fetch user-customised models from DB
    stmt = (
        select(AiModel)
        .where(and_(AiModel.provider_id == provider_id, AiModel.user_id == user_id))
        .order_by(asc(AiModel.sort), desc(AiModel.enabled), desc(AiModel.updated_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    user_map = {m.id: m for m in rows}

    # Merge with builtins
    builtins = get_builtin_models(provider_id)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for bm in builtins:
        um = user_map.get(bm.id)
        entry: dict[str, Any] = {
            "id": bm.id,
            "provider_id": provider_id,
            "display_name": (um.display_name if um and um.display_name else bm.display_name),
            "type": bm.type,
            "enabled": (um.enabled if um is not None else bm.enabled),
            "source": "builtin",
            "abilities": _model_abilities(
                provider_id,
                bm.id,
                um.abilities if um and um.abilities else bm.abilities,
            ),
            "context_window_tokens": (
                um.context_window_tokens if um and um.context_window_tokens else bm.context_window_tokens
            ),
            "description": (um.description if um and um.description else None),
            "sort": (um.sort if um else None),
        }
        merged.append(entry)
        seen.add(bm.id)

    # Append user-only (custom/remote) models
    for mid, um in user_map.items():
        if mid not in seen:
            merged.append({
                "id": um.id,
                "provider_id": um.provider_id,
                "display_name": um.display_name,
                "type": um.type,
                "enabled": um.enabled,
                "source": um.source,
                "abilities": _model_abilities(um.provider_id, um.id, um.abilities),
                "context_window_tokens": um.context_window_tokens,
                "description": um.description,
                "sort": um.sort,
            })

    # Filters
    if enabled is not None:
        merged = [m for m in merged if m["enabled"] == enabled]
    if model_type:
        merged = [m for m in merged if m["type"] == model_type]

    # Pagination
    merged = merged[offset:]
    if limit is not None:
        merged = merged[:limit]

    return merged


async def update_model(
    session: AsyncSession,
    user_id: str,
    model_id: str,
    provider_id: str,
    **values: Any,
) -> None:
    """Upsert model (update on conflict)."""
    values.pop("id", None)
    values.pop("provider_id", None)
    values.pop("user_id", None)
    values["updated_at"] = _now()

    stmt = pg_insert(AiModel).values(
        id=model_id,
        provider_id=provider_id,
        user_id=user_id,
        **values,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AiModel.id, AiModel.provider_id, AiModel.user_id],
        set_=values,
    )
    await session.execute(stmt)


async def toggle_model_enabled(
    session: AsyncSession,
    user_id: str,
    model_id: str,
    provider_id: str,
    enabled: bool,
    model_type: Optional[str] = None,
) -> None:
    values: dict[str, Any] = {"enabled": enabled, "updated_at": _now()}
    if model_type:
        values["type"] = model_type

    stmt = pg_insert(AiModel).values(
        id=model_id,
        provider_id=provider_id,
        user_id=user_id,
        **values,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AiModel.id, AiModel.provider_id, AiModel.user_id],
        set_=values,
    )
    await session.execute(stmt)


async def batch_toggle_models(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    model_ids: list[str],
    enabled: bool,
) -> None:
    if not model_ids:
        return
    for mid in model_ids:
        await toggle_model_enabled(session, user_id, mid, provider_id, enabled)


async def delete_model(
    session: AsyncSession,
    user_id: str,
    model_id: str,
    provider_id: str,
) -> None:
    await session.execute(
        delete(AiModel).where(
            and_(
                AiModel.id == model_id,
                AiModel.provider_id == provider_id,
                AiModel.user_id == user_id,
            )
        )
    )


async def clear_models_by_provider(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
) -> None:
    await session.execute(
        delete(AiModel).where(
            and_(AiModel.provider_id == provider_id, AiModel.user_id == user_id)
        )
    )


async def clear_remote_models(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
) -> None:
    await session.execute(
        delete(AiModel).where(
            and_(
                AiModel.provider_id == provider_id,
                AiModel.source == "remote",
                AiModel.user_id == user_id,
            )
        )
    )


async def update_model_order(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    sort_map: list[dict[str, Any]],
) -> None:
    if not sort_map:
        return
    for item in sort_map:
        values: dict[str, Any] = {"sort": item["sort"], "updated_at": _now()}
        if item.get("type"):
            values["type"] = item["type"]
        stmt = pg_insert(AiModel).values(
            id=item["id"],
            provider_id=provider_id,
            user_id=user_id,
            enabled=True,
            **values,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AiModel.id, AiModel.provider_id, AiModel.user_id],
            set_=values,
        )
        await session.execute(stmt)


# ─────────────────────────────────────────────────────────────────────
#  Runtime state (used by chat to resolve which providers are active)
# ─────────────────────────────────────────────────────────────────────

async def get_runtime_state(
    session: AsyncSession,
    user_id: str,
    vault: Optional[KeyVaultService] = None,
) -> dict[str, Any]:
    """Return the runtime state needed by the SPA and chat engine.

    Mirrors the TS ``getAiProviderRuntimeState``.
    """
    providers = await get_provider_list(session, user_id)
    enabled_providers = [p for p in providers if p.get("enabled")]

    # Fetch all user models
    all_models_stmt = (
        select(AiModel)
        .where(AiModel.user_id == user_id)
    )
    all_models_rows = (await session.execute(all_models_stmt)).scalars().all()

    # Build enabled models list (merge with builtins)
    enabled_model_list: list[dict[str, Any]] = []
    enabled_provider_ids = {p["id"] for p in enabled_providers}
    user_model_map: dict[str, AiModel] = {}
    for m in all_models_rows:
        user_model_map[f"{m.provider_id}:{m.id}"] = m

    for provider in enabled_providers:
        pid = provider["id"]
        for bm in get_builtin_models(pid):
            key = f"{pid}:{bm.id}"
            um = user_model_map.pop(key, None)
            entry = {
                "id": bm.id,
                "provider_id": pid,
                "display_name": (um.display_name if um and um.display_name else bm.display_name),
                "type": bm.type,
                "enabled": (um.enabled if um is not None else bm.enabled),
                "abilities": _model_abilities(
                    pid,
                    bm.id,
                    um.abilities if um and um.abilities else bm.abilities,
                ),
            }
            enabled_model_list.append(entry)

    # Append remaining custom/remote models from enabled providers
    for key, um in user_model_map.items():
        if um.provider_id in enabled_provider_ids:
            enabled_model_list.append({
                "id": um.id,
                "provider_id": um.provider_id,
                "display_name": um.display_name,
                "type": um.type,
                "enabled": um.enabled,
                "abilities": _model_abilities(um.provider_id, um.id, um.abilities),
            })

    # Runtime config per provider
    runtime_config: dict[str, Any] = {}
    kv_stmt = (
        select(AiProvider.id, AiProvider.key_vaults, AiProvider.config,
               AiProvider.settings, AiProvider.fetch_on_client)
        .where(AiProvider.user_id == user_id)
    )
    kv_rows = (await session.execute(kv_stmt)).all()
    for row in kv_rows:
        kv = {}
        if row.key_vaults and vault:
            kv = vault.decrypt_json(row.key_vaults)
        runtime_config[row.id] = {
            "config": row.config or {},
            "fetch_on_client": row.fetch_on_client,
            "key_vaults": kv,
            "settings": row.settings or {},
        }

    enabled_models_final = [m for m in enabled_model_list if m.get("enabled")]

    return {
        "enabledAiModels": enabled_models_final,
        "enabledAiProviders": [
            {"id": p["id"], "name": p["name"], "logo": p.get("logo"), "source": p["source"]}
            for p in enabled_providers
        ],
        "enabledChatAiProviders": [
            {"id": p["id"], "name": p["name"], "logo": p.get("logo"), "source": p["source"]}
            for p in enabled_providers
            if any(m["provider_id"] == p["id"] and m.get("type") == "chat" for m in enabled_models_final)
        ],
        "runtimeConfig": runtime_config,
    }

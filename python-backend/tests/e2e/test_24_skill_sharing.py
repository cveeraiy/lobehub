"""Phase 13c — Skill Sharing & Access Control.

Tests visibility (private/public/restricted), cross-user sharing,
and authorization guards.

Requires two Keycloak test users:
  - User A (default: chandra) — skill owner
  - User B (env: E2E_KC_USERNAME_B / E2E_KC_PASSWORD_B) — share recipient
"""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e

# ── Helpers ──────────────────────────────────────────────────────────

_SKILL_COUNTER = 0
_RUN_ID = id(object())  # unique per pytest session


def _unique_skill(visibility: str = "private") -> dict:
    global _SKILL_COUNTER
    _SKILL_COUNTER += 1
    return {
        "identifier": f"e2e-share-skill-{_RUN_ID}-{_SKILL_COUNTER}",
        "name": f"E2E Share Skill {_RUN_ID}-{_SKILL_COUNTER}",
        "description": f"Skill for sharing tests ({visibility})",
        "visibility": visibility,
    }


# ── 1. Visibility defaults ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_skill_default_visibility(client: httpx.AsyncClient) -> None:
    """Skill created without explicit visibility defaults to 'private'."""
    r = await client.post("/api/skills", json={
        "identifier": "e2e-vis-default",
        "name": "Vis Default",
        "description": "Test default visibility",
    })
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 200
    assert r2.json()["visibility"] == "private"

    # Cleanup
    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_create_skill_explicit_visibility(client: httpx.AsyncClient) -> None:
    """Skill created with explicit visibility='public'."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 200
    assert r2.json()["visibility"] == "public"

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_create_skill_invalid_visibility(client: httpx.AsyncClient) -> None:
    """Skill creation with invalid visibility returns 400."""
    r = await client.post("/api/skills", json={
        "identifier": "e2e-vis-bad",
        "name": "Bad Vis",
        "description": "Invalid",
        "visibility": "invalid_value",
    })
    assert r.status_code == 400


# ── 2. Visibility update ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_visibility_endpoint(client: httpx.AsyncClient) -> None:
    """PUT /{skill_id}/visibility changes the visibility."""
    r = await client.post("/api/skills", json=_unique_skill("private"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client.put(f"/api/skills/{skill_id}/visibility", json={"visibility": "public"})
    assert r2.status_code == 200
    assert r2.json()["visibility"] == "public"

    r3 = await client.get(f"/api/skills/{skill_id}")
    assert r3.json()["visibility"] == "public"

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_update_visibility_invalid(client: httpx.AsyncClient) -> None:
    """PUT /{skill_id}/visibility with bad value returns 400."""
    r = await client.post("/api/skills", json=_unique_skill("private"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client.put(f"/api/skills/{skill_id}/visibility", json={"visibility": "wrong"})
    assert r2.status_code == 400

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_set_private_clears_shares(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
) -> None:
    """Setting visibility to private removes all share records."""
    r = await client.post("/api/skills", json=_unique_skill("restricted"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # Share with user B
    await client.post(f"/api/skills/{skill_id}/share", json={"user_ids": [user_id_b]})

    shares = (await client.get(f"/api/skills/{skill_id}/shares")).json()
    assert len(shares) == 1

    # Set to private → shares should be cleared
    await client.put(f"/api/skills/{skill_id}/visibility", json={"visibility": "private"})

    shares2 = (await client.get(f"/api/skills/{skill_id}/shares")).json()
    assert len(shares2) == 0

    await client.delete(f"/api/skills/{skill_id}")


# ── 3. Private skill isolation ──────────────────────────────────────

@pytest.mark.asyncio
async def test_private_skill_invisible_to_other_user(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """Private skill is NOT visible to User B."""
    r = await client.post("/api/skills", json=_unique_skill("private"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # User B cannot get it by ID
    r2 = await client_b.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 404

    # User B cannot see it in list
    r3 = await client_b.get("/api/skills?source=user")
    user_b_ids = {s["id"] for s in r3.json()}
    assert skill_id not in user_b_ids

    await client.delete(f"/api/skills/{skill_id}")


# ── 4. Public skill visibility ──────────────────────────────────────

@pytest.mark.asyncio
async def test_public_skill_visible_to_other_user(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """Public skill IS visible to User B."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # User B can get it by ID
    r2 = await client_b.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 200
    assert r2.json()["visibility"] == "public"

    # User B can see it in list (source=shared or default)
    r3 = await client_b.get("/api/skills?source=shared")
    shared_ids = {s["id"] for s in r3.json()}
    assert skill_id in shared_ids

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_public_skill_not_in_owner_shared_list(
    client: httpx.AsyncClient,
) -> None:
    """Owner's own public skill is NOT in source=shared (it's in source=user)."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client.get("/api/skills?source=shared")
    shared_ids = {s["id"] for s in r2.json()}
    assert skill_id not in shared_ids

    r3 = await client.get("/api/skills?source=user")
    user_ids = {s["id"] for s in r3.json()}
    assert skill_id in user_ids

    await client.delete(f"/api/skills/{skill_id}")


# ── 5. Restricted sharing ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_share_skill_with_user_b(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
    state: SharedState,
) -> None:
    """Share a restricted skill with User B → User B can access it."""
    r = await client.post("/api/skills", json=_unique_skill("restricted"))
    assert r.status_code == 201
    skill_id = r.json()["id"]
    state.shared_skill_id = skill_id

    # Share with user B
    r2 = await client.post(f"/api/skills/{skill_id}/share", json={"user_ids": [user_id_b]})
    assert r2.status_code == 201
    assert user_id_b in r2.json()["shared_with"]

    # User B can now access it
    r3 = await client_b.get(f"/api/skills/{skill_id}")
    assert r3.status_code == 200
    assert r3.json()["visibility"] == "restricted"


@pytest.mark.asyncio
async def test_share_auto_sets_restricted(
    client: httpx.AsyncClient,
    user_id_b: str,
) -> None:
    """Sharing a private skill auto-upgrades visibility to 'restricted'."""
    r = await client.post("/api/skills", json=_unique_skill("private"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # Verify it starts as private
    r2 = await client.get(f"/api/skills/{skill_id}")
    assert r2.json()["visibility"] == "private"

    # Share → should auto-upgrade to restricted
    await client.post(f"/api/skills/{skill_id}/share", json={"user_ids": [user_id_b]})

    r3 = await client.get(f"/api/skills/{skill_id}")
    assert r3.json()["visibility"] == "restricted"

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_restricted_skill_invisible_to_unshared_user(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """Restricted skill with NO shares is invisible to User B."""
    r = await client.post("/api/skills", json=_unique_skill("restricted"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 404

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_list_shares(
    client: httpx.AsyncClient,
    user_id_b: str,
    state: SharedState,
) -> None:
    """List shares for a skill returns the shared users."""
    if not state.shared_skill_id:
        pytest.skip("No shared skill")

    r = await client.get(f"/api/skills/{state.shared_skill_id}/shares")
    assert r.status_code == 200
    shares = r.json()
    shared_user_ids = [s["shared_with_user_id"] for s in shares]
    assert user_id_b in shared_user_ids


@pytest.mark.asyncio
async def test_duplicate_share_is_idempotent(
    client: httpx.AsyncClient,
    user_id_b: str,
    state: SharedState,
) -> None:
    """Sharing the same skill with the same user again does not create duplicates."""
    if not state.shared_skill_id:
        pytest.skip("No shared skill")

    r = await client.post(
        f"/api/skills/{state.shared_skill_id}/share",
        json={"user_ids": [user_id_b]},
    )
    assert r.status_code == 201
    # Already shared → should not appear in created list
    assert user_id_b not in r.json()["shared_with"]


@pytest.mark.asyncio
async def test_share_self_is_skipped(
    client: httpx.AsyncClient,
    user_id: str,
    state: SharedState,
) -> None:
    """Sharing with yourself is silently skipped."""
    if not state.shared_skill_id:
        pytest.skip("No shared skill")

    r = await client.post(
        f"/api/skills/{state.shared_skill_id}/share",
        json={"user_ids": [user_id]},
    )
    assert r.status_code == 201
    assert user_id not in r.json()["shared_with"]


# ── 6. Unshare ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unshare_skill(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
    state: SharedState,
) -> None:
    """Unshare a skill from User B → User B loses access."""
    if not state.shared_skill_id:
        pytest.skip("No shared skill")

    r = await client.post(
        f"/api/skills/{state.shared_skill_id}/unshare",
        json={"user_ids": [user_id_b]},
    )
    assert r.status_code == 200

    # User B can no longer access it
    r2 = await client_b.get(f"/api/skills/{state.shared_skill_id}")
    assert r2.status_code == 404

    # Shares list should be empty
    r3 = await client.get(f"/api/skills/{state.shared_skill_id}/shares")
    assert len(r3.json()) == 0


# ── 7. Authorization guards ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_owner_cannot_update_skill(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
) -> None:
    """User B cannot update a skill owned by User A (even if public)."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # User B tries to update → should fail (owner-only check on update)
    r2 = await client_b.put(f"/api/skills/{skill_id}", json={
        "manifest": {"name": "hacked"},
    })
    # Update uses user_id filter, so it silently does nothing (returns 200)
    # but the skill is unchanged
    r3 = await client.get(f"/api/skills/{skill_id}")
    assert r3.json()["display_name"] != "hacked"

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_non_owner_cannot_delete_skill(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
) -> None:
    """User B cannot delete a skill owned by User A."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    # User B tries to delete → silently no-op (owner-only filter)
    await client_b.delete(f"/api/skills/{skill_id}")

    # Skill still exists for owner
    r2 = await client.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 200

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_non_owner_cannot_share(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
    user_id_b: str,
    user_id: str,
) -> None:
    """User B cannot share User A's skill (even if public)."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.post(f"/api/skills/{skill_id}/share", json={"user_ids": [user_id]})
    assert r2.status_code == 404  # "not owned by you"

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_non_owner_cannot_change_visibility(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """User B cannot change visibility of User A's skill."""
    r = await client.post("/api/skills", json=_unique_skill("public"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.put(f"/api/skills/{skill_id}/visibility", json={"visibility": "private"})
    assert r2.status_code == 404

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_non_owner_cannot_list_shares(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """User B cannot list share records of User A's skill."""
    r = await client.post("/api/skills", json=_unique_skill("restricted"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.get(f"/api/skills/{skill_id}/shares")
    assert r2.status_code == 404

    await client.delete(f"/api/skills/{skill_id}")


# ── 8. Search includes shared/public ────────────────────────────────

@pytest.mark.asyncio
async def test_search_finds_public_skill(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """Search by User B finds a public skill created by User A."""
    r = await client.post("/api/skills", json={
        "identifier": "e2e-search-pub",
        "name": "SearchablePublicSkill",
        "description": "A public skill for search test",
        "visibility": "public",
    })
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.get("/api/skills/search/query?q=SearchablePublic")
    assert r2.status_code == 200
    found_ids = {s["id"] for s in r2.json()}
    assert skill_id in found_ids

    await client.delete(f"/api/skills/{skill_id}")


@pytest.mark.asyncio
async def test_search_excludes_private_skill(
    client: httpx.AsyncClient,
    client_b: httpx.AsyncClient,
) -> None:
    """Search by User B does NOT find a private skill created by User A."""
    r = await client.post("/api/skills", json={
        "identifier": "e2e-search-priv",
        "name": "SearchablePrivateSkill",
        "description": "A private skill for search test",
        "visibility": "private",
    })
    assert r.status_code == 201
    skill_id = r.json()["id"]

    r2 = await client_b.get("/api/skills/search/query?q=SearchablePrivate")
    assert r2.status_code == 200
    found_ids = {s["id"] for s in r2.json()}
    assert skill_id not in found_ids

    await client.delete(f"/api/skills/{skill_id}")


# ── 9. Cascade delete ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_skill_cascades_shares(
    client: httpx.AsyncClient,
    user_id_b: str,
) -> None:
    """Deleting a skill removes its share records (FK CASCADE)."""
    r = await client.post("/api/skills", json=_unique_skill("restricted"))
    assert r.status_code == 201
    skill_id = r.json()["id"]

    await client.post(f"/api/skills/{skill_id}/share", json={"user_ids": [user_id_b]})
    shares = (await client.get(f"/api/skills/{skill_id}/shares")).json()
    assert len(shares) == 1

    # Delete the skill
    await client.delete(f"/api/skills/{skill_id}")

    # Skill is gone
    r2 = await client.get(f"/api/skills/{skill_id}")
    assert r2.status_code == 404


# ── 10. Cleanup shared_skill_id from state ──────────────────────────

@pytest.mark.asyncio
async def test_cleanup_shared_skill(
    client: httpx.AsyncClient,
    state: SharedState,
) -> None:
    """Cleanup: delete the shared skill created earlier in test_share_skill_with_user_b."""
    if state.shared_skill_id:
        await client.delete(f"/api/skills/{state.shared_skill_id}")
        state.shared_skill_id = None

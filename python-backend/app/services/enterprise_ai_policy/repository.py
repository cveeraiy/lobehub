"""Repository contracts for enterprise AI policies.

Phase 1 intentionally avoids database schema changes. Implementations may be
static, in-memory, or dev-only JSON backed while the REST contract and runtime
enforcement are tested.
"""

from __future__ import annotations

from typing import Protocol

from .types import EnterpriseAiPolicy


class EnterpriseAiPolicyRepository(Protocol):
    async def list_policies(self) -> list[EnterpriseAiPolicy]: ...

    async def upsert_policy(self, policy: EnterpriseAiPolicy) -> EnterpriseAiPolicy: ...

    async def delete_policy(self, policy_id: str) -> None: ...

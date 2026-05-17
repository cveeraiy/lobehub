"""Key-vault encryption for provider API keys.

Wire-compatible with the TS ``KeyVaultsGateKeeper`` which uses AES-256-GCM
via the Web Crypto API.  The encrypted format is::

    <hex_iv>:<hex_auth_tag>:<hex_ciphertext>

The ``KEY_VAULTS_SECRET`` env var must be a 32-byte (256-bit) key encoded as
base64 (generate with ``openssl rand -base64 32``).
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

logger = logging.getLogger(__name__)


class KeyVaultService:
    """Encrypt / decrypt provider key-vault JSON using AES-256-GCM."""

    _singleton: "KeyVaultService | None" = None

    def __init__(self, raw_key: bytes) -> None:
        if len(raw_key) not in (16, 24, 32):
            raise ValueError(
                f"KEY_VAULTS_SECRET must be 16, 24, or 32 bytes when base64-decoded, "
                f"got {len(raw_key)} bytes.  Run `openssl rand -base64 32` to create one."
            )
        self._aesgcm = AESGCM(raw_key)

    # ── Factory ──────────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "KeyVaultService":
        """Return a cached singleton built from the ``KEY_VAULTS_SECRET`` env var."""
        if cls._singleton is not None:
            return cls._singleton
        secret = settings.key_vaults_secret
        if not secret:
            raise RuntimeError(
                "KEY_VAULTS_SECRET is not set.  "
                "Run `openssl rand -base64 32` and add it to your .env."
            )
        raw_key = base64.urlsafe_b64decode(secret + "=")
        cls._singleton = cls(raw_key)
        return cls._singleton

    # ── Encrypt / Decrypt ────────────────────────────────────────────
    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return the hex-encoded ``iv:tag:ct`` string.

        Wire-compatible with the TS KeyVaultsGateKeeper.encrypt().
        """
        iv = os.urandom(12)  # 96-bit nonce recommended for GCM
        # AESGCM.encrypt returns ciphertext || tag (tag is last 16 bytes)
        ct_with_tag = self._aesgcm.encrypt(iv, plaintext.encode(), None)
        ct = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        return f"{iv.hex()}:{tag.hex()}:{ct.hex()}"

    def decrypt(self, encrypted: str) -> tuple[str, bool]:
        """Decrypt the ``iv:tag:ct`` string.

        Returns ``(plaintext, was_authentic)``.  On failure returns
        ``("", False)`` rather than raising — mirrors the TS behaviour.
        """
        parts = encrypted.split(":")
        if len(parts) != 3:
            return ("", False)
        try:
            iv = bytes.fromhex(parts[0])
            tag = bytes.fromhex(parts[1])
            ct = bytes.fromhex(parts[2])
            # AESGCM.decrypt expects ciphertext || tag
            plaintext_bytes = self._aesgcm.decrypt(iv, ct + tag, None)
            return (plaintext_bytes.decode(), True)
        except Exception:
            return ("", False)

    # ── Convenience helpers ──────────────────────────────────────────
    def encrypt_json(self, data: dict[str, Any]) -> str:
        """Serialise *data* to JSON and encrypt."""
        return self.encrypt(json.dumps(data, separators=(",", ":")))

    def decrypt_json(self, encrypted: str | None) -> dict[str, Any]:
        """Decrypt and parse JSON.  Returns ``{}`` on any failure."""
        if not encrypted:
            return {}
        plaintext, ok = self.decrypt(encrypted)
        if not ok or not plaintext:
            return {}
        try:
            return json.loads(plaintext)
        except json.JSONDecodeError:
            logger.warning("Failed to parse decrypted key-vault JSON")
            return {}

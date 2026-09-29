"""Encryption at rest for credentials (plan §29).

`ENCRYPTION_KEYS` is a comma-separated list of Fernet keys: the FIRST encrypts, ALL decrypt, which
allows rotation without downtime. Each ciphertext is stored with the `key_id` (a short fingerprint
of the key that encrypted it) so rows still on an old key can be found and re-encrypted.

There is no fallback key: the application refuses to start without valid keys.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class DecryptionError(Exception):
    """Ciphertext could not be decrypted with any configured key."""


@dataclass(frozen=True, slots=True)
class Encrypted:
    ciphertext: bytes
    key_id: str


def key_fingerprint(key: str) -> str:
    """Stable, non-reversible 16-hex-char identifier of a key (safe to store and log)."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class Encryptor:
    def __init__(self, keys: Sequence[str]) -> None:
        if not keys:
            raise ValueError("at least one encryption key is required")
        self._fernets = [Fernet(k.encode()) for k in keys]
        self._multi = MultiFernet(self._fernets)
        self.active_key_id = key_fingerprint(keys[0])

    def encrypt(self, plaintext: bytes) -> Encrypted:
        return Encrypted(self._fernets[0].encrypt(plaintext), self.active_key_id)

    def decrypt(self, ciphertext: bytes) -> bytes:
        try:
            return self._multi.decrypt(ciphertext)
        except InvalidToken as exc:
            raise DecryptionError(
                "stored secret cannot be decrypted with the configured keys"
            ) from exc

    def needs_rotation(self, key_id: str) -> bool:
        return key_id != self.active_key_id

    def rotate(self, ciphertext: bytes) -> Encrypted:
        """Re-encrypt with the active key."""
        try:
            return Encrypted(self._multi.rotate(ciphertext), self.active_key_id)
        except InvalidToken as exc:
            raise DecryptionError(
                "stored secret cannot be decrypted with the configured keys"
            ) from exc

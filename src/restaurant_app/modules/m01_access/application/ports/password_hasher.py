"""Port for password hashing; implemented by the Argon2 adapter (RNF-02)."""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    """One-way password hashing contract; never store cleartext (RNF-02)."""

    def hash(self, password: str) -> str:
        """Return an opaque hash suitable for persistence."""
        ...

    def verify(self, password: str, hash_: str) -> bool:
        """Return *True* when *password* matches the stored *hash_*."""
        ...

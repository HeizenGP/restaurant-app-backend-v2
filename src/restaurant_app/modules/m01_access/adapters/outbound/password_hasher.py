"""Argon2id adapter for the password-hashing port."""

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError


class Argon2PasswordHasher:
    """Use pwdlib's current Argon2id recommendation without exposing its format."""

    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()
        self._dummy_hash = self._password_hash.hash("m01-internal-dummy-password")

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, hash_: str) -> bool:
        try:
            return self._password_hash.verify(password, hash_)
        except PwdlibError:
            return False

    def verify_dummy(self, password: str) -> None:
        """Reduce account-enumeration timing without exposing a real account hash."""

        self.verify(password, self._dummy_hash)

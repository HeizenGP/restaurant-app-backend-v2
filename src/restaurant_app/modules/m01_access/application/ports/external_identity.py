"""Port for verifying external identity assertions."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    subject: str
    email: str
    display_name: str
    avatar_url: str | None = None


class GoogleIdentityVerifier(Protocol):
    async def verify(self, id_token: str) -> GoogleIdentity:
        """Verify signature, issuer, audience, expiry and verified email."""
        ...

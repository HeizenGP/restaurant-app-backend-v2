"""Domain-level error hierarchy for M01 access."""

from __future__ import annotations


class AccessError(Exception):
    """Base class for M01 access errors."""


class InvalidCredentialsError(AccessError):
    """Email or password is incorrect (CA-M01-01-02)."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class EmailAlreadyRegisteredError(AccessError):
    """The email address is already in use."""

    def __init__(self, email: str) -> None:
        super().__init__(f"Email already registered: {email}")
        self.email = email


class UserNotFoundError(AccessError):
    """No user exists with the given identifier."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"User not found: {identifier}")


class UserInactiveError(AccessError):
    """The user account has been deactivated."""

    def __init__(self) -> None:
        super().__init__("User account is inactive")


class SessionExpiredError(AccessError):
    """The authentication session has expired or been revoked."""

    def __init__(self) -> None:
        super().__init__("Session expired or revoked")


class InvalidTokenError(AccessError):
    """The provided token is invalid or malformed."""

    def __init__(self, reason: str = "Invalid token") -> None:
        super().__init__(reason)


class ExternalAuthenticationError(AccessError):
    """The external identity assertion is invalid or cannot be safely linked."""

    def __init__(self, detail: str = "Google authentication could not be completed") -> None:
        super().__init__(detail)


class AuthenticationProviderUnavailableError(AccessError):
    """An optional authentication provider is not configured."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider} authentication is not configured")


class InvalidPasswordResetTokenError(AccessError):
    """A password reset token is invalid, expired or already used."""

    def __init__(self) -> None:
        super().__init__("Invalid or expired password reset token")


class RoleAlreadyAssignedError(AccessError):
    """The user already has the specified role."""

    def __init__(self, user_id: str, role: str) -> None:
        super().__init__(f"Role {role} already assigned to user {user_id}")


class AuthorizationError(AccessError):
    """The caller lacks the required permissions (CA-M01-05-02, RNF-01)."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(detail)

"""Safety checks for destructive PostgreSQL integration tests."""

import pytest

from tests.integration.test_initial_migration import _test_database_target


def test_destructive_database_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_DSN",
        "postgresql+asyncpg://restaurant_app:secret@localhost/restaurant_app_test",
    )
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_TEST_DATABASE", raising=False)

    with pytest.raises(pytest.fail.Exception, match="must equal the exact"):
        _test_database_target()


def test_destructive_database_rejects_non_test_database_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_DSN",
        "postgresql+asyncpg://restaurant_app:secret@localhost/restaurant_app",
    )
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DATABASE", "restaurant_app")

    with pytest.raises(pytest.fail.Exception, match="ending in"):
        _test_database_target()


def test_destructive_database_accepts_explicit_stage07_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_DSN",
        "postgresql+asyncpg://restaurant_app:secret@localhost/restaurant_app_stage07",
    )
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DATABASE", "restaurant_app_stage07")

    assert _test_database_target() == (
        "postgresql://restaurant_app:secret@localhost/restaurant_app_stage07",
        "restaurant_app_stage07",
    )


def test_destructive_database_rejects_generic_truthy_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_DSN",
        "postgresql://restaurant_app:secret@localhost/restaurant_app_test",
    )
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DATABASE", "true")

    with pytest.raises(pytest.fail.Exception, match="must equal the exact"):
        _test_database_target()

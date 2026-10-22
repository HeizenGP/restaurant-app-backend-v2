"""Unit tests for simulated payment method validation."""

import pytest

from restaurant_app.modules.m06_payments.domain.errors import InvalidPaymentRequestError
from restaurant_app.modules.m06_payments.domain.payment_methods import validate_collection_method


@pytest.mark.parametrize(
    ("method", "reference", "expected"),
    [
        (" efectivo ", None, ("EFECTIVO", None)),
        ("yape", "987654321", ("YAPE", "987654321")),
        ("PLIN", "912345678", ("PLIN", "912345678")),
        ("tarjeta", "123456789", ("TARJETA", "123456789")),
    ],
)
def test_valid_methods(
    method: str, reference: str | None, expected: tuple[str, str | None]
) -> None:
    assert validate_collection_method(method, reference) == expected


@pytest.mark.parametrize(
    ("method", "reference"),
    [
        ("SIMULADO", None),
        ("BITCOIN", None),
        ("EFECTIVO", "123456789"),
        ("YAPE", None),
        ("YAPE", "12345678"),
        ("YAPE", "123456789"),
        ("YAPE", "９87654321"),
        ("YAPE", "98765432a"),
        ("YAPE", "987-654-321"),
        ("PLIN", "9999999999"),
        ("TARJETA", None),
        ("TARJETA", "1234"),
        ("TARJETA", "1234567890123456"),
        ("TARJETA", "12345678a"),
    ],
)
def test_invalid_methods(method: str, reference: str | None) -> None:
    with pytest.raises(InvalidPaymentRequestError):
        validate_collection_method(method, reference)

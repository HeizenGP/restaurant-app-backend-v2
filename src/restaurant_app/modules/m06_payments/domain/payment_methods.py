"""Validate simulated collection methods without collecting bank-card details."""

import re

from restaurant_app.modules.m06_payments.domain.errors import InvalidPaymentRequestError

ALLOWED_METHODS = frozenset({"EFECTIVO", "YAPE", "PLIN", "TARJETA"})


def validate_collection_method(
    method_code: str, reference_code: str | None
) -> tuple[str, str | None]:
    """Validate payment method and optional non-sensitive simulated reference."""
    method = method_code.strip().upper()
    if method not in ALLOWED_METHODS:
        raise InvalidPaymentRequestError(
            "method_code must be EFECTIVO, YAPE, PLIN or TARJETA"
        )
    if method == "EFECTIVO":
        if reference_code is not None:
            raise InvalidPaymentRequestError("EFECTIVO does not accept reference_code")
        return method, None
    if reference_code is None:
        raise InvalidPaymentRequestError("This method requires reference_code")
    if method in {"YAPE", "PLIN"}:
        if re.fullmatch(r"9[0-9]{8}", reference_code) is None:
            raise InvalidPaymentRequestError(
                "YAPE and PLIN require a 9-digit cellphone beginning with 9"
            )
    elif re.fullmatch(r"[0-9]{9}", reference_code) is None:
        raise InvalidPaymentRequestError(
            "TARJETA requires a simulated 9-digit operation reference, not a card number"
        )
    return method, reference_code

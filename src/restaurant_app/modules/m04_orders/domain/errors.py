"""Expected M04 request errors, independent of HTTP."""


class OrderError(Exception):
    pass


class InvalidOrderError(OrderError):
    pass


class OrderNotFoundError(OrderError):
    pass


class ProductUnavailableError(OrderError):
    pass


class OrderConflictError(OrderError):
    pass

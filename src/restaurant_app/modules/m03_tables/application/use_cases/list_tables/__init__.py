"""M03 table reads."""

from restaurant_app.modules.m03_tables.application.use_cases.list_tables.handler import (
    GetTable,
    ListTables,
)

__all__ = ["GetTable", "ListTables"]

"""Add Google identity binding and password recovery tokens.

Revision ID: 20261106_0007
Revises: 20261106_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0007"
down_revision: str | Sequence[str] | None = "20261106_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_users_password_hash_not_blank", "users", schema="public", type_="check")
    op.add_column(
        "users",
        sa.Column("google_subject", sa.String(length=255), nullable=True),
        schema="public",
    )
    op.alter_column("users", "password_hash", nullable=True, schema="public")
    op.create_check_constraint(
        "ck_users_password_hash_not_blank",
        "users",
        "password_hash IS NULL OR btrim(password_hash) <> ''",
        schema="public",
    )
    op.create_check_constraint(
        "ck_users_has_authentication_method",
        "users",
        "password_hash IS NOT NULL OR google_subject IS NOT NULL",
        schema="public",
    )
    op.create_unique_constraint(
        "uq_users_google_subject", "users", ["google_subject"], schema="public"
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="ck_password_reset_tokens_expiry"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        schema="public",
    )
    op.create_index(
        "ix_password_reset_tokens_user_created",
        "password_reset_tokens",
        ["user_id", "created_at"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_user_created",
        table_name="password_reset_tokens",
        schema="public",
    )
    op.drop_table("password_reset_tokens", schema="public")
    op.execute(
        "UPDATE public.users SET password_hash = '$argon2id$disabled-google-account' "
        "WHERE password_hash IS NULL"
    )
    op.drop_constraint("uq_users_google_subject", "users", schema="public", type_="unique")
    op.drop_constraint(
        "ck_users_has_authentication_method", "users", schema="public", type_="check"
    )
    op.drop_constraint("ck_users_password_hash_not_blank", "users", schema="public", type_="check")
    op.alter_column("users", "password_hash", nullable=False, schema="public")
    op.drop_column("users", "google_subject", schema="public")
    op.create_check_constraint(
        "ck_users_password_hash_not_blank",
        "users",
        "btrim(password_hash) <> ''",
        schema="public",
    )

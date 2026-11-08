"""Seed super admin user heizen.gp27@gmail.com with password and SUPER_ADMIN role.

Revision ID: 20261107_0011
Revises: 20261107_0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261107_0011"
down_revision: str | Sequence[str] | None = "20261107_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_SUPERADMIN_SQL = """
DO $$
DECLARE
    v_user_id UUID;
    v_password_hash TEXT := '$argon2id$v=19$m=65536,t=3,p=4$JTFMVeRmkBKzkTTpF+CUjg$NdTg7OVjr+jdKP2l9dvRy/ACeoS/Gv8ZQDBZaug6O9c';
BEGIN
    SELECT id INTO v_user_id FROM public.users WHERE lower(email) = 'heizen.gp27@gmail.com';

    IF v_user_id IS NULL THEN
        v_user_id := '7a000000-0000-4000-a000-000000000001';
        INSERT INTO public.users (id, display_name, email, password_hash, is_active)
        VALUES (v_user_id, 'Heizen Super Admin', 'heizen.gp27@gmail.com', v_password_hash, TRUE);
    ELSE
        UPDATE public.users
        SET password_hash = v_password_hash,
            display_name = 'Heizen Super Admin',
            is_active = TRUE
        WHERE id = v_user_id;
    END IF;

    -- Ensure SUPER_ADMIN role is assigned
    INSERT INTO public.user_roles (user_id, role_code)
    VALUES (v_user_id, 'SUPER_ADMIN')
    ON CONFLICT (user_id, role_code) DO NOTHING;

    -- Also ensure ADMIN role is assigned
    INSERT INTO public.user_roles (user_id, role_code)
    VALUES (v_user_id, 'ADMIN')
    ON CONFLICT (user_id, role_code) DO NOTHING;
END $$;
"""

REVERT_SUPERADMIN_SQL = """
DELETE FROM public.user_roles WHERE user_id IN (
    SELECT id FROM public.users WHERE lower(email) = 'heizen.gp27@gmail.com'
);
DELETE FROM public.users WHERE lower(email) = 'heizen.gp27@gmail.com';
"""


def upgrade() -> None:
    op.execute(SEED_SUPERADMIN_SQL)


def downgrade() -> None:
    op.execute(REVERT_SUPERADMIN_SQL)

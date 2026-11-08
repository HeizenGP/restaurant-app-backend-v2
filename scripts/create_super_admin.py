#!/usr/bin/env python3
"""Script to seed or reset the SUPER_ADMIN user in KAIRO."""

import argparse
import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select

from restaurant_app.core.config import get_settings
from restaurant_app.core.database import create_database_resources, session_scope
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel, UserRoleModel
from restaurant_app.modules.m01_access.adapters.outbound.password_hasher import Argon2PasswordHasher


async def create_super_admin(email: str, password: str, display_name: str) -> None:
    settings = get_settings()
    resources = create_database_resources(settings)
    hasher = Argon2PasswordHasher()

    clean_email = email.strip().lower()
    hashed_pwd = hasher.hash(password)

    try:
        async with session_scope(resources) as session:
            # Check if user already exists
            query = select(UserModel).where(UserModel.email == clean_email)
            existing_user = (await session.execute(query)).scalar_one_or_none()

            if existing_user:
                print(f"[KAIRO] Usuario existente encontrado: '{existing_user.email}' (ID: {existing_user.id})")
                existing_user.password_hash = hashed_pwd
                existing_user.display_name = display_name
                existing_user.is_active = True
                user_id = existing_user.id
            else:
                user_id = str(uuid4())
                new_user = UserModel(
                    id=user_id,
                    display_name=display_name,
                    email=clean_email,
                    password_hash=hashed_pwd,
                    is_active=True,
                )
                session.add(new_user)
                await session.flush()
                print(f"[KAIRO] Nuevo usuario creado: '{clean_email}' (ID: {user_id})")

            # Check if SUPER_ADMIN role already assigned
            role_query = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_code == "SUPER_ADMIN",
            )
            has_role = (await session.execute(role_query)).scalar_one_or_none()

            if not has_role:
                session.add(UserRoleModel(user_id=user_id, role_code="SUPER_ADMIN"))
                print("[KAIRO] Rol 'SUPER_ADMIN' asignado exitosamente.")
            else:
                print("[KAIRO] El usuario ya contaba con el rol 'SUPER_ADMIN'.")

            await session.commit()

        print("\n" + "=" * 50)
        print(" SUPER_ADMIN CONFIGURADO CON ÉXITO")
        print("=" * 50)
        print(f" Correo:      {clean_email}")
        print(f" Contraseña:  {password}")
        print(f" Rol:         SUPER_ADMIN (Acceso Total)")
        print("=" * 50 + "\n")

    finally:
        await resources.dispose()


def main():
    parser = argparse.ArgumentParser(description="Crear o actualizar Super Admin de KAIRO")
    parser.add_argument("--email", default="heizen.gp27@gmail.com", help="Email del Super Admin")
    parser.add_argument("--password", default="12345678", help="Contraseña")
    parser.add_argument("--name", default="Heizen Super Admin", help="Nombre a mostrar")

    args = parser.parse_args()
    asyncio.run(create_super_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()

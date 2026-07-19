#!/usr/bin/env python3
"""OIHK Basic — first-run setup script.

Creates the data directory, initializes the database, and bootstraps
an admin account if configured.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="OIHK Basic setup")
    parser.add_argument("--install-deps", action="store_true", help="Install Python dependencies")
    parser.add_argument("--init-db", action="store_true", help="Initialize database tables")
    parser.add_argument("--create-admin", action="store_true", help="Create bootstrap admin account")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    backend_dir = project_root / "backend"

    if args.install_deps:
        print("Installing Python dependencies...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=backend_dir,
        )
        print("Dependencies installed.")

    if args.init_db:
        print("Initializing database...")
        sys.path.insert(0, str(backend_dir))
        from app.core.config import get_settings
        from app.database import engine, Base
        from app import models  # noqa: F401

        import asyncio

        async def _init():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"Database initialized at: {get_settings().database_url}")

        asyncio.run(_init())

    if args.create_admin:
        print("Creating admin bootstrap account...")
        sys.path.insert(0, str(backend_dir))
        from app.core.config import get_settings
        from app.database import SessionLocal
        from app.services.auth_service import register_user

        import asyncio

        async def _create_admin():
            settings = get_settings()
            if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
                print("ERROR: Set OIHK_BOOTSTRAP_ADMIN_EMAIL and OIHK_BOOTSTRAP_ADMIN_PASSWORD in .env")
                return False
            async with SessionLocal() as session:
                try:
                    user = await register_user(
                        session,
                        email=settings.bootstrap_admin_email,
                        username="admin",
                        password=settings.bootstrap_admin_password,
                        role="admin",
                    )
                    await session.commit()
                    print(f"Admin account created: {user.email}")
                    return True
                except Exception as e:
                    print(f"Error creating admin: {e}")
                    return False

        asyncio.run(_create_admin())

    print("\nSetup complete! Run the server with: uvicorn app.main:app --host 127.0.0.1 --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())

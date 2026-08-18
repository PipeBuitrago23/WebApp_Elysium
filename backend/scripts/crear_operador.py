#!/usr/bin/env python
"""CLI para crear un operador (superadmin de la plataforma) — la identidad con
la que se administran TODOS los tenants desde el panel superadmin (Fase 3).
Sirve para dar de alta el primer operador (bootstrap), ya que el login del
panel necesita al menos uno para poder entrar.

Se conecta directo con DATABASE_URL (el rol dueño/superuser que bypassa RLS),
igual que crear_tenant.py y Alembic — NUNCA con APP_DATABASE_URL. La tabla
`operadores` no tiene RLS, pero `app_user` (el rol de runtime) fue REVOKEado
de ella en la migración 0006, así que solo la conexión DATABASE_URL puede
escribirla. Usa su propio engine/sesión, no importa database.py.

Uso:
    python scripts/crear_operador.py --email dueno@plataforma.com --nombre "Felipe"

    python scripts/crear_operador.py --email dueno@plataforma.com --nombre "Felipe" --dry-run
"""
import argparse
import os
import re
import secrets
import sys
import uuid

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import MAX_PASSWORD_BYTES  # noqa: E402
from models.operador import Operador  # noqa: E402

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://admin:password_seguro@db:5432/elysium_agenda")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un operador (superadmin de plataforma).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Valida y muestra qué se crearía, sin escribir nada")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not _EMAIL_RE.match(email):
        print(f"✗ Email inválido: {email!r}")
        sys.exit(1)

    engine = create_engine(_database_url())
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        if db.query(Operador).filter(Operador.email == email).first():
            print(f"✗ Ya existe un operador con email {email!r}.")
            sys.exit(1)

        print("✓ Validaciones OK — se crearía:")
        print(f"  Operador: email={email!r} nombre={args.nombre!r}")

        if args.dry_run:
            print("\n(--dry-run: no se escribió nada)")
            return

        password = secrets.token_urlsafe(12)
        hashed = bcrypt.hashpw(password.encode()[:MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode()

        db.add(Operador(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hashed,
            nombre=args.nombre,
        ))
        db.commit()
        print(f"\n✓ Operador '{email}' creado.")
        print(f"  Contraseña temporal: {password}")
        print("  Guárdala ahora — no se vuelve a mostrar ni se guarda en texto plano.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

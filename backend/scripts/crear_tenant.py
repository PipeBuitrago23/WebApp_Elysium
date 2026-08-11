#!/usr/bin/env python
"""CLI para dar de alta un tenant nuevo: crea su fila en `tenants`, sus 2
`servicios` por defecto (Pilates/Fisioterapia, misma capacidad/duración base
que Elysium) y un `Usuario` admin — todo en una sola transacción. Reemplaza
el SQL a mano documentado en CLAUDE.md → "Adding a new tenant".

Se conecta directo con DATABASE_URL (la misma conexión admin/dueño de tablas
que usa Alembic) — NUNCA con APP_DATABASE_URL. Un tenant que recién se está
creando no tiene contexto de RLS todavía (current_tenant_id sin setear), así
que la conexión normal de la app en runtime (app_user, no-superusuario)
dejaría que la política RLS rechace silenciosamente los INSERT vía su
WITH CHECK. DATABASE_URL bypassea RLS por completo porque su rol es dueño de
las tablas (ver backend/scripts/bootstrap_app_role.sql). Usa su propio
engine/sesión — no importa database.py, cuyo engine está atado a
APP_DATABASE_URL y al listener de tenant-context "begin", ninguno de los
cuales aplica acá.

Uso:
    python scripts/crear_tenant.py --slug pilatesmed --nombre "Pilates Medellín" \\
        --plan completo --admin-email admin@pilatesmed.com --admin-nombre "Ana Ruiz"

    python scripts/crear_tenant.py --slug pilatesmed --nombre "Pilates Medellín" \\
        --admin-email admin@pilatesmed.com --admin-nombre "Ana Ruiz" --dry-run
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

from core.constants import MAX_PASSWORD_BYTES, RESERVED_SLUGS  # noqa: E402
from models.servicio import Servicio  # noqa: E402
from models.tenant import Tenant  # noqa: E402
from models.usuario import Usuario  # noqa: E402

_SLUG_RE = re.compile(r"^[a-z0-9-]{3,30}$")

# Mismos valores base que la fila seed de Elysium (migración 0002) — un
# tenant nuevo puede editarlos después desde la tabla servicios directamente,
# no hay UI todavía.
DEFAULT_SERVICIOS = [
    {"nombre": "Pilates", "capacidad": 6, "duracion_min": 60},
    {"nombre": "Fisioterapia", "capacidad": 2, "duracion_min": 60},
]


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://admin:password_seguro@db:5432/elysium_agenda")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def validar_slug(slug: str, db) -> list[str]:
    errores = []
    if not _SLUG_RE.match(slug):
        errores.append(
            "El slug debe tener 3-30 caracteres: solo minúsculas, números y guiones ([a-z0-9-])."
        )
    if slug in RESERVED_SLUGS:
        errores.append(f"'{slug}' es un slug reservado ({', '.join(sorted(RESERVED_SLUGS))}).")
    if db.query(Tenant).filter(Tenant.slug == slug).first():
        errores.append(f"Ya existe un tenant con slug '{slug}'.")
    return errores


def main() -> None:
    parser = argparse.ArgumentParser(description="Da de alta un tenant nuevo (tenant + servicios + admin).")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--nombre", required=True, help="Nombre comercial")
    parser.add_argument("--plan", choices=["basico", "completo"], default="basico")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-nombre", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Valida y muestra qué se crearía, sin escribir nada")
    args = parser.parse_args()

    slug = args.slug.strip().lower()

    engine = create_engine(_database_url())
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        errores = validar_slug(slug, db)
        if errores:
            for e in errores:
                print(f"✗ {e}")
            sys.exit(1)

        print("✓ Validaciones OK — se crearía:")
        print(f"  Tenant:   slug={slug!r} nombre={args.nombre!r} plan={args.plan!r}")
        for s in DEFAULT_SERVICIOS:
            print(f"  Servicio: {s['nombre']} (capacidad={s['capacidad']}, duracion_min={s['duracion_min']})")
        print(f"  Admin:    email={args.admin_email!r} nombre={args.admin_nombre!r}")

        if args.dry_run:
            print("\n(--dry-run: no se escribió nada)")
            return

        password = secrets.token_urlsafe(12)
        hashed = bcrypt.hashpw(password.encode()[:MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode()

        tenant = Tenant(
            id=str(uuid.uuid4()),
            slug=slug,
            nombre_comercial=args.nombre,
            plan=args.plan,
            estado="activo",
            timezone="America/Bogota",
            branding={},
            config={},
            features_override={},
        )
        db.add(tenant)
        db.flush()  # necesita tenant.id para las FKs de abajo

        for s in DEFAULT_SERVICIOS:
            db.add(Servicio(tenant_id=tenant.id, activo=True, **s))

        db.add(Usuario(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=args.admin_email,
            hashed_password=hashed,
            nombre=args.admin_nombre,
            es_admin=True,
        ))

        db.commit()
        print(f"\n✓ Tenant '{slug}' creado.")
        print(f"  Contraseña temporal del admin ({args.admin_email}): {password}")
        print("  Guárdala ahora — no se vuelve a mostrar ni se guarda en texto plano.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

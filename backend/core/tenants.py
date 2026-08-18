"""Alta de tenants — lógica compartida por el CLI (scripts/crear_tenant.py) y
el endpoint del panel superadmin (routes/superadmin_tenants.py). Ambos crean
exactamente lo mismo (tenant + 2 servicios base + usuario admin) llamando a
`crear_tenant`, así que la validación y la creación viven en un solo lugar.

Las funciones reciben una `Session` (no crean engine): el caller la provee y
controla la transacción. Esa sesión DEBE estar atada a una conexión que
bypasee RLS (DATABASE_URL — superuser/owner), porque un tenant recién creado
no tiene contexto RLS y los INSERT de servicios/usuarios serían rechazados por
la política WITH CHECK bajo app_user. Ver el docstring de
scripts/crear_tenant.py y core/superadmin_db.py.
"""
import re
import secrets
import uuid

import bcrypt
from sqlalchemy.orm import Session

from core.constants import MAX_PASSWORD_BYTES, RESERVED_SLUGS
from models.servicio import Servicio
from models.tenant import Tenant
from models.usuario import Usuario

SLUG_RE = re.compile(r"^[a-z0-9-]{3,30}$")
PLANES_VALIDOS = {"basico", "completo"}
ESTADOS_TENANT = {"trial", "activo", "suspendido"}

# Mismos valores base que la fila seed de Elysium (migración 0002).
DEFAULT_SERVICIOS = [
    {"nombre": "Pilates", "capacidad": 6, "duracion_min": 60},
    {"nombre": "Fisioterapia", "capacidad": 2, "duracion_min": 60},
]


def validar_slug(db: Session, slug: str) -> list[str]:
    """Lista de errores legibles (vacía = OK). Formato, slug reservado y
    unicidad. Se comparte para que CLI y endpoint rechacen los mismos inputs."""
    errores = []
    if not SLUG_RE.match(slug):
        errores.append(
            "El slug debe tener 3-30 caracteres: solo minúsculas, números y guiones ([a-z0-9-])."
        )
    if slug in RESERVED_SLUGS:
        errores.append(f"'{slug}' es un slug reservado ({', '.join(sorted(RESERVED_SLUGS))}).")
    if db.query(Tenant).filter(Tenant.slug == slug).first():
        errores.append(f"Ya existe un tenant con slug '{slug}'.")
    return errores


def crear_tenant(
    db: Session,
    *,
    slug: str,
    nombre: str,
    plan: str,
    admin_email: str,
    admin_nombre: str,
) -> tuple[Tenant, str]:
    """Crea tenant + 2 servicios + usuario admin en la sesión dada, SIN
    commitear (el caller controla la transacción). Devuelve el Tenant y la
    contraseña temporal generada del admin (se muestra una sola vez, nunca se
    guarda en texto plano). Asume que `slug` ya pasó por `validar_slug`."""
    password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(password.encode()[:MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode()

    tenant = Tenant(
        id=str(uuid.uuid4()),
        slug=slug,
        nombre_comercial=nombre,
        plan=plan,
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
        email=admin_email,
        hashed_password=hashed,
        nombre=admin_nombre,
        es_admin=True,
    ))
    return tenant, password

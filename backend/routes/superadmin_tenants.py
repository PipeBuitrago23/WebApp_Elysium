import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from auth.superadmin import require_superadmin
from core.superadmin_db import get_superadmin_db
from core.tenants import ESTADOS_TENANT, PLANES_VALIDOS, crear_tenant, validar_slug
from models.operador import Operador
from models.servicio import Servicio
from models.tenant import Tenant

router = APIRouter()

# Toda acción que cree/suspenda/cambie el plan de un tenant se loguea acá — es
# la superficie de más privilegio del sistema. En producción va a los logs de
# Railway. Nunca se loguean contraseñas ni hashes.
#
# Handler propio a nivel INFO: la auditoría es un requisito de seguridad, no
# puede depender de la config de logging de uvicorn (que deja el root en
# WARNING → un .info() de un logger sin handler propio se perdería). propagate
# =False evita doble emisión si el root llegara a tener un handler.
audit = logging.getLogger("superadmin.audit")
if not audit.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [SUPERADMIN-AUDIT] %(message)s"))
    audit.addHandler(_h)
    audit.setLevel(logging.INFO)
    audit.propagate = False

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _log(operador: Operador, accion: str, slug: str, detalle: str = "") -> None:
    audit.info("operador=%s accion=%s tenant=%s %s", operador.email, accion, slug, detalle)


# ── Schemas ──────────────────────────────────────────────────────────────────

class TenantListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    nombre_comercial: str
    plan: str
    estado: str
    created_at: datetime


class ServicioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nombre: str
    capacidad: int
    duracion_min: int
    activo: bool


class TenantDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    nombre_comercial: str
    plan: str
    estado: str
    timezone: str
    custom_domain: str | None
    branding: dict
    config: dict
    features_override: dict
    created_at: datetime
    servicios: list[ServicioOut]


class TenantCreate(BaseModel):
    slug: str
    nombre: str
    plan: str = "basico"
    admin_email: str
    admin_nombre: str

    @field_validator("slug")
    @classmethod
    def _slug_lower(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("plan")
    @classmethod
    def _plan_valido(cls, v: str) -> str:
        if v not in PLANES_VALIDOS:
            raise ValueError(f"plan debe ser uno de: {', '.join(sorted(PLANES_VALIDOS))}")
        return v

    @field_validator("admin_email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("admin_email inválido")
        return v


class TenantCreateOut(BaseModel):
    slug: str
    nombre_comercial: str
    plan: str
    admin_email: str
    admin_password_temporal: str


class TenantUpdate(BaseModel):
    """PATCH parcial: solo los campos presentes se tocan. branding/config/
    features_override se REEMPLAZAN por completo por el valor enviado (no se
    hace merge parcial) — el caller manda el objeto completo que quiere guardar;
    `Tenant.get_config` ya mergea config sobre DEFAULT_CONFIG al leer."""
    plan: str | None = None
    estado: str | None = None
    branding: dict | None = None
    config: dict | None = None
    features_override: dict | None = None

    @field_validator("plan")
    @classmethod
    def _plan_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in PLANES_VALIDOS:
            raise ValueError(f"plan debe ser uno de: {', '.join(sorted(PLANES_VALIDOS))}")
        return v

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in ESTADOS_TENANT:
            raise ValueError(f"estado debe ser uno de: {', '.join(sorted(ESTADOS_TENANT))}")
        return v


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_tenant_or_404(db: Session, slug: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")
    return tenant


def _detalle(db: Session, tenant: Tenant) -> TenantDetail:
    # La sesión de superadmin bypassa RLS (DATABASE_URL), así que puede leer los
    # servicios de cualquier tenant sin setear app.tenant_id.
    servicios = db.query(Servicio).filter(Servicio.tenant_id == tenant.id).all()
    return TenantDetail(
        slug=tenant.slug,
        nombre_comercial=tenant.nombre_comercial,
        plan=tenant.plan,
        estado=tenant.estado,
        timezone=tenant.timezone,
        custom_domain=tenant.custom_domain,
        branding=tenant.branding or {},
        config=tenant.config or {},
        features_override=tenant.features_override or {},
        created_at=tenant.created_at,
        servicios=[ServicioOut.model_validate(s) for s in servicios],
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TenantListItem])
def listar_tenants(
    db: Session = Depends(get_superadmin_db),
    _: Operador = Depends(require_superadmin),
):
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.get("/{slug}", response_model=TenantDetail)
def detalle_tenant(
    slug: str,
    db: Session = Depends(get_superadmin_db),
    _: Operador = Depends(require_superadmin),
):
    return _detalle(db, _get_tenant_or_404(db, slug))


@router.post("/", response_model=TenantCreateOut, status_code=status.HTTP_201_CREATED)
def crear_tenant_endpoint(
    data: TenantCreate,
    db: Session = Depends(get_superadmin_db),
    operador: Operador = Depends(require_superadmin),
):
    errores = validar_slug(db, data.slug)
    if errores:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errores)

    tenant, password = crear_tenant(
        db, slug=data.slug, nombre=data.nombre, plan=data.plan,
        admin_email=data.admin_email, admin_nombre=data.admin_nombre,
    )
    db.commit()
    _log(operador, "crear_tenant", data.slug, f"plan={data.plan} admin={data.admin_email}")
    return TenantCreateOut(
        slug=tenant.slug,
        nombre_comercial=tenant.nombre_comercial,
        plan=tenant.plan,
        admin_email=data.admin_email,
        admin_password_temporal=password,
    )


@router.patch("/{slug}", response_model=TenantDetail)
def actualizar_tenant(
    slug: str,
    data: TenantUpdate,
    db: Session = Depends(get_superadmin_db),
    operador: Operador = Depends(require_superadmin),
):
    tenant = _get_tenant_or_404(db, slug)
    cambios: list[str] = []

    if data.plan is not None and data.plan != tenant.plan:
        cambios.append(f"plan {tenant.plan}->{data.plan}")
        tenant.plan = data.plan
    if data.estado is not None and data.estado != tenant.estado:
        cambios.append(f"estado {tenant.estado}->{data.estado}")
        tenant.estado = data.estado
    if data.branding is not None:
        tenant.branding = data.branding
        cambios.append("branding")
    if data.config is not None:
        tenant.config = data.config
        cambios.append("config")
    if data.features_override is not None:
        tenant.features_override = data.features_override
        cambios.append("features_override")

    if cambios:
        db.commit()
        _log(operador, "actualizar_tenant", slug, "cambios=" + ", ".join(cambios))
        db.refresh(tenant)

    return _detalle(db, tenant)

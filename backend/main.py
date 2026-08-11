import asyncio
import logging
import os
import re
import uuid
import bcrypt
from contextlib import asynccontextmanager
from datetime import date, timedelta
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.features import require_feature
from limiter import limiter
from database import SessionLocal, current_tenant_id
from middleware.tenant import TenantMiddleware
from models.paciente import Paciente
from models.usuario import Usuario
from models.cita import Cita
from models.pago import Pago
from models.tenant import Tenant
from routes import auth as auth_router
from routes import pacientes
from routes import citas
from routes import pagos
from routes import portal
from routes import medicos
from routes import medico_portal
from routes import ventas
from routes import gastos
from routes import tenant as tenant_router
from routes.citas import procesar_citas_vencidas
from services.email import send_recordatorio

logger = logging.getLogger(__name__)

JOB_INTERVALO_SEG = 5 * 60  # run every 5 minutes


def _resolve_elysium_tenant():
    """Looks up the Elysium tenant with no RLS context needed (tenants has
    no RLS). Uses its own short-lived session — deliberately NOT reused for
    the tenant-scoped work that follows, because that first transaction has
    already begun (and its "begin" event already fired) before we know the
    tenant_id, so `current_tenant_id` must be set BEFORE a fresh session
    opens its own transaction, not mid-transaction on this one."""
    db = SessionLocal()
    try:
        return db.query(Tenant).filter(Tenant.slug == "elysium").first()
    finally:
        db.close()


def _seed_admin():
    """Dev/demo convenience seed — pre-multi-tenant, still hardcoded to the
    Elysium tenant. Will move into a proper onboarding flow in a later phase."""
    tenant = _resolve_elysium_tenant()
    if not tenant:
        logger.warning("Tenant 'elysium' no existe todavía — se omite el seed de admin.")
        return

    hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    token = current_tenant_id.set(str(tenant.id))
    db = SessionLocal()
    try:
        if not db.query(Usuario).filter(
            Usuario.tenant_id == tenant.id, Usuario.email == "admin@elysium.com"
        ).first():
            db.add(Usuario(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email="admin@elysium.com",
                hashed_password=hashed,
                nombre="Administrador",
                es_admin=True,
            ))
            db.commit()
    finally:
        db.close()
        current_tenant_id.reset(token)


def _seed_paciente():
    """Seed a test patient account for portal demo/testing (same caveat as
    _seed_admin — hardcoded to the Elysium tenant for now)."""
    CEDULA = "00000001"
    EMAIL  = "paciente@elysium.com"

    tenant = _resolve_elysium_tenant()
    if not tenant:
        logger.warning("Tenant 'elysium' no existe todavía — se omite el seed de paciente.")
        return

    token = current_tenant_id.set(str(tenant.id))
    db = SessionLocal()
    try:
        if not db.get(Paciente, (tenant.id, CEDULA)):
            db.add(Paciente(
                tenant_id=tenant.id,
                Paciente=CEDULA,
                nombre="Carlos Pérez",
                email=EMAIL,
                telefono="3001234567",
            ))

        if not db.query(Usuario).filter(Usuario.tenant_id == tenant.id, Usuario.email == EMAIL).first():
            hashed = bcrypt.hashpw(b"paciente123", bcrypt.gensalt()).decode()
            db.add(Usuario(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email=EMAIL,
                hashed_password=hashed,
                nombre="Carlos Pérez",
                es_admin=False,
            ))

        if not db.query(Pago).filter(Pago.tenant_id == tenant.id, Pago.paciente_id == CEDULA).first():
            fecha_pago = date.today() - timedelta(days=5)
            db.add(Pago(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                paciente_id=CEDULA,
                tipo_paquete="Pilates",
                total_sesiones=12,
                sesiones_restantes=8,
                fecha_pago=fecha_pago,
                fecha_inicio=fecha_pago,
                fecha_vencimiento=fecha_pago + timedelta(days=45),
            ))

        db.commit()
    finally:
        db.close()
        current_tenant_id.reset(token)


def _active_tenants() -> list[Tenant]:
    db = SessionLocal()
    try:
        return db.query(Tenant).filter(Tenant.estado == "activo").all()
    finally:
        db.close()


async def _job_citas_vencidas():
    """Background loop: auto-penalize past appointments with no status update.

    Runs outside any request, so there's no TenantMiddleware to resolve a
    tenant — it must loop over every active tenant itself, setting
    current_tenant_id for each in turn. Without this, RLS (enabled on citas/
    pagos) would make every tenant's rows invisible to this job."""
    while True:
        await asyncio.sleep(JOB_INTERVALO_SEG)
        try:
            tenants = _active_tenants()
        except Exception as exc:
            logger.error("Job citas vencidas: no se pudo listar tenants activos: %s", exc)
            continue
        for tenant in tenants:
            token = current_tenant_id.set(str(tenant.id))
            db = SessionLocal()
            try:
                n = procesar_citas_vencidas(db)
                if n:
                    logger.info(
                        "Job: %d cita(s) marcadas como penalización automáticamente (tenant=%s).",
                        n, tenant.slug,
                    )
            except Exception as exc:
                logger.error("Job citas vencidas (tenant=%s): %s", tenant.slug, exc)
            finally:
                db.close()
                current_tenant_id.reset(token)


async def _job_recordatorios():
    """Background loop: send 24h reminder emails for tomorrow's appointments.
    Same per-tenant looping requirement as _job_citas_vencidas."""
    while True:
        await asyncio.sleep(60 * 60)  # run every hour
        manana = date.today() + timedelta(days=1)
        try:
            tenants = _active_tenants()
        except Exception as exc:
            logger.error("Job recordatorios: no se pudo listar tenants activos: %s", exc)
            continue
        for tenant in tenants:
            token = current_tenant_id.set(str(tenant.id))
            db = SessionLocal()
            try:
                pendientes = (
                    db.query(Cita)
                    .filter(
                        Cita.fecha == manana,
                        Cita.recordatorio_enviado == False,  # noqa: E712
                        Cita.estado.in_(["programada", "confirmada"]),
                    )
                    .all()
                )
                for cita in pendientes:
                    pac = db.get(Paciente, (tenant.id, cita.paciente_id))
                    if pac and pac.email:
                        plan = None if cita.tipo == "Sesión de cortesía" else (
                            db.query(Pago)
                            .filter(
                                Pago.tenant_id == tenant.id,
                                Pago.paciente_id == cita.paciente_id,
                                Pago.tipo_paquete == cita.tipo,
                                Pago.fecha_vencimiento >= manana,
                                Pago.sesiones_restantes > 0,
                            )
                            .order_by(Pago.fecha_vencimiento.asc())
                            .first()
                        )
                        send_recordatorio(pac.nombre, pac.email, cita, tenant, plan)
                    cita.recordatorio_enviado = True
                if pendientes:
                    db.commit()
                    logger.info(
                        "Job recordatorios: %d enviado(s) para %s (tenant=%s).",
                        len(pendientes), manana, tenant.slug,
                    )
            except Exception as exc:
                logger.error("Job recordatorios (tenant=%s): %s", tenant.slug, exc)
            finally:
                db.close()
                current_tenant_id.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed entirely by Alembic now (see backend/alembic/) — the
    # container's start command runs `alembic upgrade head` before uvicorn,
    # so by the time this runs the schema is already at the latest revision.
    _seed_admin()
    _seed_paciente()
    task_vencidas      = asyncio.create_task(_job_citas_vencidas())
    task_recordatorios = asyncio.create_task(_job_recordatorios())
    yield
    task_vencidas.cancel()
    task_recordatorios.cancel()
    for task in (task_vencidas, task_recordatorios):
        try:
            await task
        except asyncio.CancelledError:
            pass


_IS_PROD = os.getenv("RAILWAY_ENVIRONMENT") == "production"

app = FastAPI(
    title="Elysium Agenda API",
    lifespan=lifespan,
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None,
    openapi_url=None if _IS_PROD else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Local dev always gets an explicit origin (no real subdomain to regex-match
# against). Every <slug>.<BASE_DOMAIN> origin is additionally allowed via
# allow_origin_regex once BASE_DOMAIN is set — Starlette evaluates
# allow_origins and allow_origin_regex together, not exclusively. Never
# allow_origins=["*"]: that's incompatible with allow_credentials=True and
# would accept any origin.
_BASE_DOMAIN = os.getenv("BASE_DOMAIN", "")
ALLOWED_ORIGINS = ["http://localhost:3000"]
ALLOWED_ORIGIN_REGEX = (
    rf"^https://[a-z0-9-]+\.{re.escape(_BASE_DOMAIN)}$" if _BASE_DOMAIN else None
)

app.add_middleware(TenantMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(pacientes.router, prefix="/pacientes", tags=["pacientes"])
app.include_router(citas.router, prefix="/citas", tags=["citas"])
app.include_router(pagos.router, prefix="/pagos", tags=["pagos"])
app.include_router(portal.router, prefix="/portal", tags=["portal"])
app.include_router(tenant_router.router, prefix="/tenant", tags=["tenant"])

# Tier "completo" only — see core/features.py:PLAN_FEATURES. Tier "basico"
# routers (citas, pacientes, pagos, portal, auth) are available to every
# plan, so they're intentionally NOT gated here.
app.include_router(
    medicos.router, prefix="/medicos", tags=["medicos"],
    dependencies=[Depends(require_feature("medicos"))],
)
app.include_router(
    medico_portal.router, prefix="/medico", tags=["medico-portal"],
    dependencies=[Depends(require_feature("medico_portal"))],
)
app.include_router(
    ventas.router, prefix="/ventas", tags=["ventas"],
    dependencies=[Depends(require_feature("ventas"))],
)
app.include_router(
    gastos.router, prefix="/gastos", tags=["gastos"],
    dependencies=[Depends(require_feature("gastos"))],
)


@app.get("/health")
def health():
    return {"status": "ok"}

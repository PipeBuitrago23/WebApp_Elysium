import asyncio
import logging
import os
import uuid
import bcrypt
from contextlib import asynccontextmanager
from datetime import date, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from limiter import limiter
from sqlalchemy import text
from database import Base, engine, SessionLocal
from models.paciente import Paciente  # noqa: F401
from models.usuario import Usuario
from models.cita import Cita          # noqa: F401 — needed so create_all picks up the table
from models.pago import Pago          # noqa: F401
from routes import auth as auth_router
from routes import pacientes
from routes import citas
from routes import pagos
from routes import portal
from routes.citas import procesar_citas_vencidas
from services.email import send_recordatorio

logger = logging.getLogger(__name__)

JOB_INTERVALO_SEG = 5 * 60  # run every 5 minutes


def _run_migrations():
    """Incremental schema changes that create_all cannot handle (existing tables).
    Each statement uses IF NOT EXISTS / IF EXISTS so it is safe to run on every startup.
    """
    stmts = [
        # Added after initial deploy — must exist for the reminder job and /citas queries
        "ALTER TABLE citas ADD COLUMN IF NOT EXISTS recordatorio_enviado BOOLEAN NOT NULL DEFAULT FALSE",
        # Habeas Data — Ley 1581 de 2012
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS habeas_data_aceptado BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_aceptacion_habeas TIMESTAMP",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS habeas_data_aceptado BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS fecha_aceptacion_habeas TIMESTAMP",
    ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _seed_admin():
    hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    db = SessionLocal()
    try:
        if not db.query(Usuario).filter(Usuario.email == "admin@elysium.com").first():
            db.add(Usuario(
                id=str(uuid.uuid4()),
                email="admin@elysium.com",
                hashed_password=hashed,
                nombre="Administrador",
                es_admin=True,
            ))
            db.commit()
    finally:
        db.close()


def _seed_paciente():
    """Seed a test patient account for portal demo/testing."""
    CEDULA = "00000001"
    EMAIL  = "paciente@elysium.com"
    db = SessionLocal()
    try:
        if not db.get(Paciente, CEDULA):
            db.add(Paciente(
                Paciente=CEDULA,
                nombre="Carlos Pérez",
                email=EMAIL,
                telefono="3001234567",
            ))

        if not db.query(Usuario).filter(Usuario.email == EMAIL).first():
            hashed = bcrypt.hashpw(b"paciente123", bcrypt.gensalt()).decode()
            db.add(Usuario(
                id=str(uuid.uuid4()),
                email=EMAIL,
                hashed_password=hashed,
                nombre="Carlos Pérez",
                es_admin=False,
            ))

        if not db.query(Pago).filter(Pago.paciente_id == CEDULA).first():
            fecha_pago = date.today() - timedelta(days=5)
            db.add(Pago(
                id=str(uuid.uuid4()),
                paciente_id=CEDULA,
                tipo_paquete="Pilates",
                total_sesiones=12,
                sesiones_restantes=8,
                fecha_pago=fecha_pago,
                fecha_vencimiento=fecha_pago + timedelta(days=45),
            ))

        db.commit()
    finally:
        db.close()


async def _job_citas_vencidas():
    """Background loop: auto-penalize past appointments with no status update."""
    while True:
        await asyncio.sleep(JOB_INTERVALO_SEG)
        try:
            db = SessionLocal()
            try:
                n = procesar_citas_vencidas(db)
                if n:
                    logger.info("Job: %d cita(s) marcadas como penalización automáticamente.", n)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Job citas vencidas: %s", exc)


async def _job_recordatorios():
    """Background loop: send 24h reminder emails for tomorrow's appointments."""
    while True:
        await asyncio.sleep(60 * 60)  # run every hour
        try:
            db = SessionLocal()
            try:
                manana = date.today() + timedelta(days=1)
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
                    pac = db.get(Paciente, cita.paciente_id)
                    if pac and pac.email:
                        plan = (
                            db.query(Pago)
                            .filter(
                                Pago.paciente_id == cita.paciente_id,
                                Pago.fecha_vencimiento >= manana,
                                Pago.sesiones_restantes > 0,
                            )
                            .order_by(Pago.fecha_pago.desc())
                            .first()
                        )
                        send_recordatorio(pac.nombre, pac.email, cita, plan)
                    cita.recordatorio_enviado = True
                if pendientes:
                    db.commit()
                    logger.info("Job recordatorios: %d enviado(s) para %s.", len(pendientes), manana)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Job recordatorios: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_migrations()
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

_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(pacientes.router, prefix="/pacientes", tags=["pacientes"])
app.include_router(citas.router, prefix="/citas", tags=["citas"])
app.include_router(pagos.router, prefix="/pagos", tags=["pagos"])
app.include_router(portal.router, prefix="/portal", tags=["portal"])


@app.get("/health")
def health():
    return {"status": "ok"}

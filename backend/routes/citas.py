import uuid
from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from core.planes import descontar_sesion, plan_disponible
from database import get_db
from models.cita import Cita
from models.paciente import Paciente
from models.usuario import Usuario
from services.email import send_confirmacion

TIPOS_VALIDOS       = {"Fisioterapia", "Pilates", "Sesión de cortesía"}
CAPACIDAD           = {"Fisioterapia": 2, "Pilates": 6, "Sesión de cortesía": 6}
TURNOS              = ((time(7, 0), time(11, 0)), (time(14, 0), time(18, 0)))
ESTADOS_VALIDOS     = {"programada", "confirmada", "completada", "cancelada", "No asistió con penalización"}
ESTADOS_TERMINAL    = {"completada", "cancelada", "No asistió con penalización"}
ESTADOS_CON_DESCUENTO = {"completada", "No asistió con penalización"}
HORAS_CANCELACION   = 2


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cita_datetime(cita: Cita) -> datetime:
    return datetime.combine(cita.fecha, cita.hora)


def procesar_citas_vencidas(db: Session) -> int:
    """Auto-mark past unresolved appointments as no-show and deduct sessions.

    Only processes appointments from PREVIOUS days — today's past slots are left
    for the admin to resolve manually during the business day.
    Called by the background job every few minutes. Returns number of citas processed.
    Uses a PostgreSQL advisory lock so multiple replicas don't double-penalize.
    """
    acquired = db.execute(text("SELECT pg_try_advisory_xact_lock(20001)")).scalar()
    if not acquired:
        return 0

    hoy = date.today()

    vencidas = (
        db.query(Cita)
        .filter(
            Cita.estado.in_(["programada", "confirmada"]),
            Cita.fecha < hoy,
        )
        .all()
    )

    procesadas = 0
    for cita in vencidas:
        if cita.tipo != "Sesión de cortesía":
            descontar_sesion(db, cita.paciente_id, cita.tipo, required=False)
        cita.estado = "No asistió con penalización"
        procesadas += 1

    if procesadas:
        db.commit()
    return procesadas


# ── Schemas ──────────────────────────────────────────────────────────────────

class CitaCreate(BaseModel):
    paciente_id: str
    fecha: date
    hora: time
    tipo: str
    notas: str | None = None
    medico_id: str | None = None
    motivo_remision: str | None = None

    @field_validator("hora")
    @classmethod
    def hora_valida(cls, v: time) -> time:
        if v.minute not in (0, 30) or v.second != 0:
            raise ValueError("La hora debe ser en punto (:00) o y media (:30)")
        if not any(ini <= v <= fin for ini, fin in TURNOS):
            raise ValueError("Horario fuera de ventana permitida (07:00–11:00 · 14:00–18:00)")
        return v

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"Tipo inválido. Opciones: {', '.join(TIPOS_VALIDOS)}")
        return v


class CitaUpdate(BaseModel):
    fecha: date | None = None
    hora: time | None = None
    tipo: str | None = None
    notas: str | None = None


class EstadoUpdate(BaseModel):
    estado: str

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in ESTADOS_VALIDOS:
            raise ValueError("Estado inválido.")
        return v


class AjusteAdminBody(BaseModel):
    accion: str  # "cancelar" | "reprogramar"
    fecha: date | None = None
    hora: time | None = None

    @field_validator("accion")
    @classmethod
    def accion_valida(cls, v: str) -> str:
        if v not in ("cancelar", "reprogramar"):
            raise ValueError("Acción inválida. Use 'cancelar' o 'reprogramar'.")
        return v


class CitaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    paciente_id: str
    fecha: date
    hora: time
    tipo: str
    estado: str
    notas: str | None = None
    medico_id: str | None = None
    medico_nombre: str | None = None
    motivo_remision: str | None = None


def _citas_out(db: Session, citas: list[Cita]) -> list[CitaOut]:
    """Resolve medico_nombre for a batch of citas in a single extra query."""
    medico_ids = {c.medico_id for c in citas if c.medico_id}
    medicos = {}
    if medico_ids:
        medicos = {u.id: u.nombre for u in db.query(Usuario).filter(Usuario.id.in_(medico_ids)).all()}

    return [
        CitaOut(
            id=c.id,
            paciente_id=c.paciente_id,
            fecha=c.fecha,
            hora=c.hora,
            tipo=c.tipo,
            estado=c.estado,
            notas=c.notas,
            medico_id=c.medico_id,
            medico_nombre=medicos.get(c.medico_id),
            motivo_remision=c.motivo_remision,
        )
        for c in citas
    ]


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/", response_model=list[CitaOut])
def list_citas(
    fecha: date | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    paciente_id: str | None = Query(None),
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    q = db.query(Cita)
    if fecha:
        q = q.filter(Cita.fecha == fecha)
    if fecha_desde:
        q = q.filter(Cita.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(Cita.fecha <= fecha_hasta)
    if paciente_id:
        q = q.filter(Cita.paciente_id == paciente_id)
    if estado:
        q = q.filter(Cita.estado == estado)
    return _citas_out(db, q.order_by(Cita.fecha, Cita.hora).all())


@router.get("/{cita_id}", response_model=CitaOut)
def get_cita(
    cita_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return _citas_out(db, [row])[0]


@router.post("/", response_model=CitaOut, status_code=status.HTTP_201_CREATED)
def create_cita(
    data: CitaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if data.medico_id:
        medico = db.query(Usuario).filter(Usuario.id == data.medico_id, Usuario.es_medico == True).first()  # noqa: E712
        if not medico:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Médico no encontrado")

    # ① Active plan must cover the appointment date — citas remitidas por un médico
    # (medico_id) no lo exigen: son consultas de remisión, el paciente aún no tiene
    # paquete. "Sesión de cortesía" tampoco: nunca tiene Pago propio (ver core/planes.py).
    plan = None
    if not data.medico_id and data.tipo != "Sesión de cortesía":
        plan = plan_disponible(db, data.paciente_id, data.tipo, data.fecha)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El paciente no tiene un plan activo vigente para esa fecha.",
            )

    # ② Slot capacity
    ocupados = db.query(Cita).filter(
        Cita.fecha == data.fecha,
        Cita.hora == data.hora,
        Cita.tipo == data.tipo,
        Cita.estado.notin_(["cancelada"]),
    ).count()
    if ocupados >= CAPACIDAD[data.tipo]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot lleno para {data.tipo} el {data.fecha} a las {data.hora.strftime('%H:%M')}",
        )

    row = Cita(id=str(uuid.uuid4()), estado="programada", **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    if plan:
        db.refresh(plan)  # plan was expired by the commit above; reload before detach

    pac = db.get(Paciente, data.paciente_id)
    if pac and pac.email:
        background_tasks.add_task(send_confirmacion, pac.nombre, pac.email, row, plan)

    return _citas_out(db, [row])[0]


@router.patch("/{cita_id}/estado", response_model=CitaOut)
def patch_estado(
    cita_id: str,
    data: EstadoUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    cita = db.get(Cita, cita_id)
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    # Terminal states are immutable
    if cita.estado in ESTADOS_TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Una cita en estado '{cita.estado}' no puede modificarse.",
        )

    nuevo = data.estado

    # 2-hour cancellation window: auto-convert to penalty
    if nuevo == "cancelada":
        if datetime.now() >= _cita_datetime(cita) - timedelta(hours=HORAS_CANCELACION):
            nuevo = "No asistió con penalización"

    # Deduct session for attended or penalized outcomes.
    # Citas remitidas por un médico no exigen plan activo (ver create_cita).
    # "Sesión de cortesía" nunca descuenta de un Pago (no tiene uno propio).
    if nuevo in ESTADOS_CON_DESCUENTO and cita.tipo != "Sesión de cortesía":
        descontar_sesion(db, cita.paciente_id, cita.tipo, required=cita.medico_id is None)

    cita.estado = nuevo
    db.commit()
    db.refresh(cita)
    return _citas_out(db, [cita])[0]


@router.patch("/{cita_id}/ajuste-admin", response_model=CitaOut)
def ajuste_admin(
    cita_id: str,
    data: AjusteAdminBody,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Cancel or reschedule without touching session count and without the 2-hour rule.
    Only available from the admin panel for exceptional cases.
    """
    cita = db.get(Cita, cita_id)
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if cita.estado in ESTADOS_TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Esta cita está en estado '{cita.estado}' y no puede ajustarse.",
        )

    if data.accion == "cancelar":
        cita.estado = "cancelada"
    else:
        if not data.fecha or not data.hora:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Se requiere fecha y hora para reprogramar.",
            )
        if data.hora.minute not in (0, 30) or data.hora.second != 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La hora debe ser :00 o :30.",
            )
        if not any(ini <= data.hora <= fin for ini, fin in TURNOS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Horario fuera de ventana permitida (07:00–11:00 · 14:00–18:00).",
            )
        ocupados = (
            db.query(Cita)
            .filter(
                Cita.fecha == data.fecha,
                Cita.hora == data.hora,
                Cita.tipo == cita.tipo,
                Cita.estado.notin_(["cancelada"]),
                Cita.id != cita_id,
            )
            .count()
        )
        if ocupados >= CAPACIDAD[cita.tipo]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ese horario ya está lleno para {cita.tipo}.",
            )
        cita.fecha = data.fecha
        cita.hora = data.hora

    db.commit()
    db.refresh(cita)
    return _citas_out(db, [cita])[0]


@router.put("/{cita_id}", response_model=CitaOut)
def update_cita(
    cita_id: str,
    data: CitaUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _citas_out(db, [row])[0]


@router.delete("/{cita_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cita(
    cita_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    db.delete(row)
    db.commit()

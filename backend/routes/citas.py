import uuid
from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import get_current_user
from database import get_db
from models.cita import Cita
from models.pago import Pago

TIPOS_VALIDOS       = {"Fisioterapia", "Pilates", "Sesión de cortesía"}
CAPACIDAD           = {"Fisioterapia": 2, "Pilates": 6, "Sesión de cortesía": 6}
HORA_MIN            = time(7, 0)
HORA_MAX            = time(18, 30)
ESTADOS_VALIDOS     = {"programada", "confirmada", "completada", "cancelada", "No asistió con penalización"}
ESTADOS_TERMINAL    = {"completada", "cancelada", "No asistió con penalización"}
ESTADOS_CON_DESCUENTO = {"completada", "No asistió con penalización"}
HORAS_CANCELACION   = 2


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cita_datetime(cita: Cita) -> datetime:
    return datetime.combine(cita.fecha, cita.hora)


def _descuenta_sesion(db: Session, paciente_id: str) -> None:
    """Deduct 1 session from the patient's most recent active plan."""
    pago = (
        db.query(Pago)
        .filter(
            Pago.paciente_id == paciente_id,
            Pago.fecha_vencimiento >= date.today(),
            Pago.sesiones_restantes > 0,
        )
        .order_by(Pago.fecha_pago.desc())
        .first()
    )
    if not pago:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El paciente no tiene sesiones disponibles en un plan activo.",
        )
    pago.sesiones_restantes -= 1


def procesar_citas_vencidas(db: Session) -> int:
    """Auto-mark past unresolved appointments as no-show and deduct sessions.

    Called by the background job every few minutes. Returns number of citas processed.
    Unlike _descuenta_sesion, does not raise if there is no active plan — just skips deduction.
    """
    hoy   = date.today()
    ahora = datetime.now().time()

    vencidas = (
        db.query(Cita)
        .filter(
            Cita.estado.in_(["programada", "confirmada"]),
            (Cita.fecha < hoy) | ((Cita.fecha == hoy) & (Cita.hora < ahora)),
        )
        .all()
    )

    procesadas = 0
    for cita in vencidas:
        pago = (
            db.query(Pago)
            .filter(
                Pago.paciente_id == cita.paciente_id,
                Pago.fecha_vencimiento >= hoy,
                Pago.sesiones_restantes > 0,
            )
            .order_by(Pago.fecha_pago.desc())
            .first()
        )
        if pago:
            pago.sesiones_restantes -= 1
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
    estado: str = "programada"
    notas: str | None = None

    @field_validator("hora")
    @classmethod
    def hora_valida(cls, v: time) -> time:
        if v.minute not in (0, 30) or v.second != 0:
            raise ValueError("La hora debe ser en punto (:00) o y media (:30)")
        if not (HORA_MIN <= v <= HORA_MAX):
            raise ValueError("Horario fuera de ventana permitida (07:00–18:30)")
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
    estado: str | None = None
    notas: str | None = None


class EstadoUpdate(BaseModel):
    estado: str

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in ESTADOS_VALIDOS:
            raise ValueError("Estado inválido.")
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
    _: dict = Depends(get_current_user),
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
    return q.order_by(Cita.fecha, Cita.hora).all()


@router.get("/{cita_id}", response_model=CitaOut)
def get_cita(
    cita_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return row


@router.post("/", response_model=CitaOut, status_code=status.HTTP_201_CREATED)
def create_cita(
    data: CitaCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    # ① Active plan must cover the appointment date
    plan = (
        db.query(Pago)
        .filter(
            Pago.paciente_id == data.paciente_id,
            Pago.fecha_vencimiento >= data.fecha,
            Pago.sesiones_restantes > 0,
        )
        .first()
    )
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

    row = Cita(id=str(uuid.uuid4()), **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{cita_id}/estado", response_model=CitaOut)
def patch_estado(
    cita_id: str,
    data: EstadoUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
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

    # Deduct session for attended or penalized outcomes
    if nuevo in ESTADOS_CON_DESCUENTO:
        _descuenta_sesion(db, cita.paciente_id)

    cita.estado = nuevo
    db.commit()
    db.refresh(cita)
    return cita


@router.put("/{cita_id}", response_model=CitaOut)
def update_cita(
    cita_id: str,
    data: CitaUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{cita_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cita(
    cita_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    row = db.get(Cita, cita_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    db.delete(row)
    db.commit()

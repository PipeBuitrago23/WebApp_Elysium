import uuid
from datetime import date, time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_medico
from database import get_db
from models.cita import Cita
from models.paciente import Paciente
from services.email import send_confirmacion

TIPOS_VALIDOS = {"Fisioterapia", "Pilates"}
CAPACIDAD     = {"Fisioterapia": 2, "Pilates": 6}
TURNOS        = ((time(7, 0), time(11, 0)), (time(14, 0), time(18, 0)))

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class MedicoCitaCreate(BaseModel):
    cedula: str
    nombre: str
    telefono: str | None = None
    email: str | None = None
    fecha: date
    hora: time
    tipo: str
    motivo_remision: str | None = None

    @field_validator("cedula", "nombre")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Este campo es requerido")
        return v

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


class MedicoCitaOut(BaseModel):
    id: str
    paciente_id: str
    paciente_nombre: str
    fecha: date
    hora: time
    tipo: str
    estado: str
    motivo_remision: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/citas", response_model=list[MedicoCitaOut])
def list_mis_citas(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_medico),
):
    citas = (
        db.query(Cita)
        .filter(Cita.medico_id == current_user["medico_id"])
        .order_by(Cita.fecha.desc(), Cita.hora.desc())
        .all()
    )
    pacientes = {
        p.Paciente: p.nombre
        for p in db.query(Paciente).filter(Paciente.Paciente.in_({c.paciente_id for c in citas})).all()
    } if citas else {}

    return [
        MedicoCitaOut(
            id=c.id,
            paciente_id=c.paciente_id,
            paciente_nombre=pacientes.get(c.paciente_id, c.paciente_id),
            fecha=c.fecha,
            hora=c.hora,
            tipo=c.tipo,
            estado=c.estado,
            motivo_remision=c.motivo_remision,
        )
        for c in citas
    ]


@router.post("/citas", response_model=MedicoCitaOut, status_code=status.HTTP_201_CREATED)
def crear_cita_medico(
    data: MedicoCitaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_medico),
):
    pac = db.get(Paciente, data.cedula)
    if not pac:
        pac = Paciente(
            Paciente=data.cedula,
            nombre=data.nombre,
            telefono=data.telefono,
            email=data.email,
        )
        db.add(pac)
        db.flush()  # asegura el INSERT de pacientes antes del INSERT de citas (FK paciente_id)

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

    row = Cita(
        id=str(uuid.uuid4()),
        paciente_id=data.cedula,
        fecha=data.fecha,
        hora=data.hora,
        tipo=data.tipo,
        estado="programada",
        medico_id=current_user["medico_id"],
        motivo_remision=data.motivo_remision,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    db.refresh(pac)

    if pac.email:
        background_tasks.add_task(send_confirmacion, pac.nombre, pac.email, row, None)

    return MedicoCitaOut(
        id=row.id,
        paciente_id=row.paciente_id,
        paciente_nombre=pac.nombre,
        fecha=row.fecha,
        hora=row.hora,
        tipo=row.tipo,
        estado=row.estado,
        motivo_remision=row.motivo_remision,
    )

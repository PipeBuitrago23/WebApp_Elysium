import uuid
from datetime import date, time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_medico
from core.servicios import capacidad, descripcion_ventana, hora_valida, tipos_validos
from database import current_tenant_id, get_db
from middleware.tenant import get_current_tenant
from models.cita import Cita
from models.paciente import Paciente
from models.tenant import Tenant
from services.email import send_confirmacion

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

    # hora/tipo validity depend on the tenant's config — checked in
    # crear_cita_medico()'s body instead (see routes/citas.py for why).


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
    tenant: Tenant = Depends(get_current_tenant),
    current_user: dict = Depends(require_medico),
):
    # Médico-referred citas never offer "Sesión de cortesía" — real servicios only.
    tipos = tipos_validos(db, tenant, incluir_cortesia=False)
    if data.tipo not in tipos:
        raise HTTPException(
            status_code=422, detail=f"Tipo inválido. Opciones: {', '.join(sorted(tipos))}"
        )
    if not hora_valida(tenant, data.hora):
        raise HTTPException(
            status_code=422, detail=f"Horario fuera de ventana permitida ({descripcion_ventana(tenant)})"
        )

    tenant_id = current_tenant_id.get()
    pac = db.get(Paciente, (tenant_id, data.cedula))
    if not pac:
        pac = Paciente(
            tenant_id=tenant_id,
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
    cap = capacidad(db, data.tipo)
    if cap is None or ocupados >= cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot lleno para {data.tipo} el {data.fecha} a las {data.hora.strftime('%H:%M')}",
        )

    row = Cita(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
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
        background_tasks.add_task(send_confirmacion, pac.nombre, pac.email, row, tenant, None)

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

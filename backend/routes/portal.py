import uuid
from datetime import date, time
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from database import get_db
from models.cita import Cita
from models.paciente import Paciente
from models.pago import Pago

TIPOS_VALIDOS = {"Fisioterapia", "Pilates", "Sesión de cortesía"}
CAPACIDAD     = {"Fisioterapia": 2, "Pilates": 6, "Sesión de cortesía": 6}
HORA_MIN      = time(7, 0)
HORA_MAX      = time(18, 30)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo_paquete: str
    total_sesiones: int
    sesiones_restantes: int
    fecha_vencimiento: date


class CitaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    fecha: date
    hora: time
    tipo: str
    estado: str


class PortalOut(BaseModel):
    paciente_id: str
    nombre: str
    plan_activo: PlanOut | None
    citas_proximas: list[CitaResumen]


class CitaPortalCreate(BaseModel):
    paciente_id: str
    fecha: date
    hora: time
    tipo: str

    @field_validator("hora")
    @classmethod
    def hora_valida(cls, v: time) -> time:
        if v.minute not in (0, 30) or v.second != 0:
            raise ValueError("La hora debe ser :00 o :30")
        if not (HORA_MIN <= v <= HORA_MAX):
            raise ValueError("Horario fuera de ventana permitida (07:00–18:30)")
        return v

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in TIPOS_VALIDOS:
            raise ValueError("Tipo de cita inválido")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/paciente/{cedula}", response_model=PortalOut)
def get_portal(cedula: str, db: Session = Depends(get_db)):
    pac = db.get(Paciente, cedula)
    if not pac:
        raise HTTPException(status_code=404, detail="No encontramos un paciente con esa cédula.")

    hoy = date.today()

    plan = (
        db.query(Pago)
        .filter(
            Pago.paciente_id == cedula,
            Pago.fecha_vencimiento >= hoy,
            Pago.sesiones_restantes > 0,
        )
        .order_by(Pago.fecha_pago.desc())
        .first()
    )

    citas = (
        db.query(Cita)
        .filter(
            Cita.paciente_id == cedula,
            Cita.fecha >= hoy,
            Cita.estado.in_(["programada", "confirmada"]),
        )
        .order_by(Cita.fecha, Cita.hora)
        .limit(5)
        .all()
    )

    return PortalOut(
        paciente_id=pac.Paciente,
        nombre=pac.nombre,
        plan_activo=plan,
        citas_proximas=citas,
    )


class RegistroCreate(BaseModel):
    nombre: str
    cedula: str
    telefono: str

    @field_validator("nombre", "cedula", "telefono")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Este campo es requerido")
        return v


@router.post("/registro", response_model=PortalOut, status_code=status.HTTP_201_CREATED)
def portal_registro(data: RegistroCreate, db: Session = Depends(get_db)):
    if db.get(Paciente, data.cedula):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un perfil con esa cédula. Ingresa con tu número de cédula.",
        )
    pac = Paciente(Paciente=data.cedula, nombre=data.nombre, telefono=data.telefono)
    db.add(pac)
    db.commit()
    db.refresh(pac)
    return PortalOut(paciente_id=pac.Paciente, nombre=pac.nombre, plan_activo=None, citas_proximas=[])


@router.post("/citas", response_model=CitaResumen, status_code=status.HTTP_201_CREATED)
def portal_crear_cita(data: CitaPortalCreate, db: Session = Depends(get_db)):
    if not db.get(Paciente, data.paciente_id):
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    if data.tipo == "Sesión de cortesía":
        ya_tiene = (
            db.query(Cita)
            .filter(
                Cita.paciente_id == data.paciente_id,
                Cita.tipo == "Sesión de cortesía",
                Cita.estado.notin_(["cancelada"]),
            )
            .first()
        )
        if ya_tiene:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una Sesión de cortesía registrada. Contacta a Elysium para adquirir un plan.",
            )
    else:
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
                detail="No tienes un plan activo vigente para esa fecha.",
            )

    ocupados = (
        db.query(Cita)
        .filter(
            Cita.fecha == data.fecha,
            Cita.hora == data.hora,
            Cita.tipo == data.tipo,
            Cita.estado.notin_(["cancelada"]),
        )
        .count()
    )
    if ocupados >= CAPACIDAD[data.tipo]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ese horario ya está lleno para {data.tipo}. Elige otro.",
        )

    row = Cita(
        id=str(uuid.uuid4()),
        paciente_id=data.paciente_id,
        fecha=data.fecha,
        hora=data.hora,
        tipo=data.tipo,
        estado="programada",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

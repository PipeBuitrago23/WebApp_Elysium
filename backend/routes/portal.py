import re
import uuid
from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from core.planes import plan_disponible
from core.servicios import capacidad, descripcion_ventana, hora_valida, tipos_validos
from database import current_tenant_id, get_db
from limiter import limiter
from middleware.tenant import get_current_tenant
from models.cita import Cita
from models.paciente import Paciente
from models.pago import Pago
from models.tenant import Tenant
from services.email import send_confirmacion

ESTADOS_TERMINAL  = {"completada", "cancelada", "No asistió con penalización"}

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
    planes_activos: list[PlanOut]
    citas_proximas: list[CitaResumen]


class CitaPortalCreate(BaseModel):
    paciente_id: str
    fecha: date
    hora: time
    tipo: str

    # hora/tipo validity depend on the tenant's config (horario, servicios) —
    # Pydantic validators run before a DB session or tenant exists, so those
    # checks moved into portal_crear_cita()'s body instead.


class CitaRecurrenteCreate(BaseModel):
    paciente_id: str
    fecha_inicio: date
    hora: time
    tipo: str
    repeticiones: int = Field(ge=2, le=12)

    # same as CitaPortalCreate — hora/tipo checked in the route body


class CitaOmitida(BaseModel):
    fecha: date
    motivo: str


class CitaRecurrenteOut(BaseModel):
    creadas: list[CitaResumen]
    omitidas: list[CitaOmitida]


class RegistroCreate(BaseModel):
    nombre: str
    cedula: str
    telefono: str
    email: str
    habeas_data_aceptado: bool = False

    @field_validator("nombre", "cedula", "telefono")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Este campo es requerido")
        return v

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("Ingresa un correo electrónico válido")
        return v

    @field_validator("habeas_data_aceptado")
    @classmethod
    def debe_aceptar(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debes aceptar el tratamiento de datos personales para continuar.")
        return v


class CancelarCitaBody(BaseModel):
    paciente_id: str


class ReprogramarCitaBody(BaseModel):
    paciente_id: str
    fecha: date
    hora: time

    # hora checked in the route body — see CitaPortalCreate


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/paciente/{cedula}", response_model=PortalOut)
def get_portal(cedula: str, db: Session = Depends(get_db)):
    pac = db.get(Paciente, (current_tenant_id.get(), cedula))
    if not pac:
        raise HTTPException(status_code=404, detail="No encontramos un paciente con esa cédula.")

    hoy = date.today()

    planes = (
        db.query(Pago)
        .filter(
            Pago.paciente_id == cedula,
            Pago.fecha_vencimiento >= hoy,
            Pago.sesiones_restantes > 0,
        )
        .order_by(Pago.fecha_vencimiento.asc())
        .all()
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
        planes_activos=planes,
        citas_proximas=citas,
    )


@router.post("/registro", response_model=PortalOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def portal_registro(request: Request, data: RegistroCreate, db: Session = Depends(get_db)):
    tenant_id = current_tenant_id.get()
    if db.get(Paciente, (tenant_id, data.cedula)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un perfil con esa cédula. Ingresa con tu número de cédula.",
        )
    if db.query(Paciente).filter(Paciente.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un perfil con ese correo electrónico.",
        )
    pac = Paciente(
        tenant_id=tenant_id,
        Paciente=data.cedula,
        nombre=data.nombre,
        telefono=data.telefono,
        email=data.email,
        habeas_data_aceptado=True,
        fecha_aceptacion_habeas=datetime.utcnow(),
    )
    db.add(pac)
    db.commit()
    db.refresh(pac)
    return PortalOut(paciente_id=pac.Paciente, nombre=pac.nombre, planes_activos=[], citas_proximas=[])


@router.post("/citas", response_model=CitaResumen, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def portal_crear_cita(
    request: Request,
    data: CitaPortalCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    tenant_id = current_tenant_id.get()
    if not db.get(Paciente, (tenant_id, data.paciente_id)):
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    tipos = tipos_validos(db, tenant)
    if data.tipo not in tipos:
        raise HTTPException(status_code=422, detail="Tipo de cita inválido")
    if not hora_valida(tenant, data.hora):
        raise HTTPException(
            status_code=422, detail=f"Horario fuera de ventana permitida ({descripcion_ventana(tenant)})"
        )

    if data.tipo == "Sesión de cortesía":
        max_por_paciente = tenant.get_config("sesion_cortesia.max_por_paciente")
        usadas = (
            db.query(Cita)
            .filter(
                Cita.paciente_id == data.paciente_id,
                Cita.tipo == "Sesión de cortesía",
                Cita.estado.notin_(["cancelada"]),
            )
            .count()
        )
        if usadas >= max_por_paciente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una Sesión de cortesía registrada. Contacta al estudio para adquirir un plan.",
            )
    else:
        plan = plan_disponible(db, data.paciente_id, data.tipo, data.fecha)
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
    cap = capacidad(db, data.tipo)
    if cap is None or ocupados >= cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ese horario ya está lleno para {data.tipo}. Elige otro.",
        )

    row = Cita(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        paciente_id=data.paciente_id,
        fecha=data.fecha,
        hora=data.hora,
        tipo=data.tipo,
        estado="programada",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    pac = db.get(Paciente, (tenant_id, data.paciente_id))
    if pac and pac.email:
        email_plan = None if data.tipo == "Sesión de cortesía" else plan_disponible(
            db, data.paciente_id, data.tipo, date.today()
        )
        background_tasks.add_task(send_confirmacion, pac.nombre, pac.email, row, tenant, email_plan)

    return row


@router.post("/citas/recurrente", response_model=CitaRecurrenteOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def portal_crear_cita_recurrente(
    request: Request,
    data: CitaRecurrenteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Agenda la misma cita semana a semana. Cada ocurrencia se valida por separado
    (plan vigente + cupo); las que no se puedan agendar se reportan en 'omitidas'
    en vez de abortar todo el lote.
    """
    tenant_id = current_tenant_id.get()
    pac = db.get(Paciente, (tenant_id, data.paciente_id))
    if not pac:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    # Recurring bookings never offer "Sesión de cortesía" — real servicios only.
    tipos = tipos_validos(db, tenant, incluir_cortesia=False)
    if data.tipo not in tipos:
        raise HTTPException(
            status_code=422,
            detail=f"Las citas recurrentes solo aplican para: {', '.join(sorted(tipos))}",
        )
    if not hora_valida(tenant, data.hora):
        raise HTTPException(
            status_code=422, detail=f"Horario fuera de ventana permitida ({descripcion_ventana(tenant)})"
        )

    creadas: list[tuple[Cita, Pago]] = []
    omitidas: list[CitaOmitida] = []

    for i in range(data.repeticiones):
        fecha = data.fecha_inicio + timedelta(weeks=i)

        plan = plan_disponible(db, data.paciente_id, data.tipo, fecha)
        if not plan:
            omitidas.append(CitaOmitida(fecha=fecha, motivo="Tu plan no está vigente para esa fecha."))
            continue

        ocupados = (
            db.query(Cita)
            .filter(
                Cita.fecha == fecha,
                Cita.hora == data.hora,
                Cita.tipo == data.tipo,
                Cita.estado.notin_(["cancelada"]),
            )
            .count()
        )
        cap = capacidad(db, data.tipo)
        if cap is None or ocupados >= cap:
            omitidas.append(CitaOmitida(fecha=fecha, motivo="Ese horario ya está lleno."))
            continue

        row = Cita(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            paciente_id=data.paciente_id,
            fecha=fecha,
            hora=data.hora,
            tipo=data.tipo,
            estado="programada",
        )
        db.add(row)
        creadas.append((row, plan))

    if creadas:
        db.commit()

    pac = db.get(Paciente, (tenant_id, data.paciente_id))  # re-fetch fresh: prior commit expired it
    for row, plan in creadas:
        db.refresh(row)
        db.refresh(plan)
        if pac and pac.email:
            background_tasks.add_task(send_confirmacion, pac.nombre, pac.email, row, tenant, plan)

    return CitaRecurrenteOut(
        creadas=[CitaResumen.model_validate(row) for row, _ in creadas],
        omitidas=omitidas,
    )


@router.post("/citas/{cita_id}/cancelar", response_model=CitaResumen)
@limiter.limit("10/minute")
def portal_cancelar_cita(
    request: Request,
    cita_id: str,
    data: CancelarCitaBody,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    cita = db.get(Cita, cita_id)
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    if cita.paciente_id != data.paciente_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para cancelar esta cita.")

    if cita.estado in ESTADOS_TERMINAL:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta cita ya no puede modificarse.")

    cita_dt = datetime.combine(cita.fecha, cita.hora)
    horas_cancelacion = tenant.get_config("ventana_cancelacion_horas")
    if datetime.now() >= cita_dt - timedelta(hours=horas_cancelacion):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es posible modificar o cancelar la cita con menos de 2 horas de anticipación. Por favor, comunícate con la recepción.",
        )

    cita.estado = "cancelada"
    db.commit()
    db.refresh(cita)
    return cita


@router.post("/citas/{cita_id}/reprogramar", response_model=CitaResumen)
@limiter.limit("10/minute")
def portal_reprogramar_cita(
    request: Request,
    cita_id: str,
    data: ReprogramarCitaBody,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    cita = db.get(Cita, cita_id)
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    if cita.paciente_id != data.paciente_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para modificar esta cita.")

    if cita.estado in ESTADOS_TERMINAL:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta cita ya no puede modificarse.")

    if not hora_valida(tenant, data.hora):
        raise HTTPException(
            status_code=422, detail=f"Horario fuera de ventana permitida ({descripcion_ventana(tenant)})"
        )

    cita_dt = datetime.combine(cita.fecha, cita.hora)
    horas_cancelacion = tenant.get_config("ventana_cancelacion_horas")
    if datetime.now() >= cita_dt - timedelta(hours=horas_cancelacion):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es posible modificar o cancelar la cita con menos de 2 horas de anticipación. Por favor, comunícate con la recepción.",
        )

    # Check capacity in new slot (excluding this same cita to avoid self-conflict)
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
    cap = capacidad(db, cita.tipo)
    if cap is None or ocupados >= cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ese horario ya está lleno para {cita.tipo}. Elige otro.",
        )

    # Verify plan covers the new date (not required for courtesy sessions)
    if cita.tipo != "Sesión de cortesía":
        plan = plan_disponible(db, cita.paciente_id, cita.tipo, data.fecha)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tu plan no está vigente para esa fecha.",
            )

    cita.fecha = data.fecha
    cita.hora = data.hora
    db.commit()
    db.refresh(cita)
    return cita

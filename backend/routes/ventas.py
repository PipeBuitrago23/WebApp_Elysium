import uuid
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from core.constants import METODOS_PAGO
from core.planes import crear_pago
from core.servicios import tipos_validos
from database import current_tenant_id, get_db
from middleware.tenant import get_current_tenant
from models.paciente import Paciente
from models.tenant import Tenant
from models.venta import Venta
from services.email import send_confirmacion_pago

# Sale category catalog — billing/catalog data, explicitly out of scope for
# this phase (same boundary as frontend/src/constants/packages.js).
CATEGORIAS_VALIDAS = {"Fisioterapia", "Pilates", "Combos", "Prendas de Vestir"}

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class PlanVentaItem(BaseModel):
    """One Pago to create alongside the Venta. The frontend resolves how many
    of these a sale implies (1 for a plain Pilates/Fisioterapia package, 2
    for a Combo split across both, 0 for Prendas de Vestir) — the backend
    only validates each tipo_paquete against the tenant's real servicios."""
    tipo_paquete: str
    sesiones: int

    @field_validator("sesiones")
    @classmethod
    def sesiones_positivas(cls, v: int) -> int:
        if v < 1:
            raise ValueError("sesiones debe ser mayor a 0")
        return v


class VentaCreate(BaseModel):
    paciente_id:    str
    nombre_paquete: str
    categoria:      str
    total_sesiones: int | None = None
    valor_total:    float
    abono:          float
    fecha_inicio:   date
    fecha_pago:     date | None = None
    metodo_pago:    str
    planes:         list[PlanVentaItem] = []

    @field_validator("categoria")
    @classmethod
    def categoria_valida(cls, v: str) -> str:
        if v not in CATEGORIAS_VALIDAS:
            raise ValueError(f"Categoría inválida. Opciones: {', '.join(CATEGORIAS_VALIDAS)}")
        return v

    @field_validator("metodo_pago")
    @classmethod
    def metodo_valido(cls, v: str) -> str:
        if v not in METODOS_PAGO:
            raise ValueError(f"Método de pago inválido. Opciones: {', '.join(METODOS_PAGO)}")
        return v

    @field_validator("abono")
    @classmethod
    def abono_no_negativo(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El abono no puede ser negativo.")
        return v

    @field_validator("valor_total")
    @classmethod
    def valor_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El valor total debe ser mayor a cero.")
        return v

    @model_validator(mode="after")
    def sin_fecha_pago_implica_sin_abono(self):
        if self.fecha_pago is None and self.abono != 0:
            raise ValueError("No puede haber abono sin fecha de pago.")
        return self


class VentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             str
    paciente_id:    str
    nombre_paquete: str
    categoria:      str
    total_sesiones: int | None
    valor_total:    float
    abono:          float
    saldo:          float
    fecha_inicio:   date
    fecha_pago:     date | None
    metodo_pago:    str
    estado:         str
    paciente_nombre: str | None = None


# ── Helper ────────────────────────────────────────────────────────────────────

def _out(v: Venta, nombre: str | None) -> VentaOut:
    return VentaOut(
        id=v.id,
        paciente_id=v.paciente_id,
        nombre_paquete=v.nombre_paquete,
        categoria=v.categoria,
        total_sesiones=v.total_sesiones,
        valor_total=v.valor_total,
        abono=v.abono,
        saldo=v.saldo,
        fecha_inicio=v.fecha_inicio,
        fecha_pago=v.fecha_pago,
        metodo_pago=v.metodo_pago,
        estado=v.estado,
        paciente_nombre=nombre,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[VentaOut])
def list_ventas(
    paciente_id: str | None = Query(None),
    categoria:   str | None = Query(None),
    estado:      str | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    q = db.query(Venta)
    if paciente_id:
        q = q.filter(Venta.paciente_id == paciente_id)
    if categoria:
        q = q.filter(Venta.categoria == categoria)
    if estado:
        q = q.filter(Venta.estado == estado)
    if fecha_desde:
        q = q.filter(Venta.fecha_pago >= fecha_desde)
    if fecha_hasta:
        q = q.filter(Venta.fecha_pago <= fecha_hasta)
    ventas = q.order_by(Venta.fecha_inicio.desc()).all()

    pac_ids  = {v.paciente_id for v in ventas}
    nombres  = {
        p.Paciente: p.nombre
        for p in db.query(Paciente).filter(Paciente.Paciente.in_(pac_ids)).all()
    }
    return [_out(v, nombres.get(v.paciente_id)) for v in ventas]


@router.post("/", response_model=VentaOut, status_code=status.HTTP_201_CREATED)
def create_venta(
    data: VentaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    _: dict = Depends(require_admin),
):
    tenant_id = current_tenant_id.get()
    pac = db.get(Paciente, (tenant_id, data.paciente_id))
    if not pac:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    if data.abono > data.valor_total:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El abono no puede superar el valor total.",
        )

    if data.planes:
        tipos = tipos_validos(db, tenant, incluir_cortesia=False)
        invalidos = [p.tipo_paquete for p in data.planes if p.tipo_paquete not in tipos]
        if invalidos:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"tipo_paquete inválido: {', '.join(invalidos)}. Opciones: {', '.join(sorted(tipos))}",
            )

    saldo  = round(data.valor_total - data.abono, 2)
    estado = "pagada" if saldo == 0 else "pendiente"

    row = Venta(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        paciente_id=data.paciente_id,
        nombre_paquete=data.nombre_paquete,
        categoria=data.categoria,
        total_sesiones=data.total_sesiones,
        valor_total=data.valor_total,
        abono=data.abono,
        saldo=saldo,
        fecha_inicio=data.fecha_inicio,
        fecha_pago=data.fecha_pago,
        metodo_pago=data.metodo_pago,
        estado=estado,
    )
    db.add(row)

    for plan in data.planes:
        crear_pago(
            db, tenant, tenant_id, data.paciente_id, plan.tipo_paquete,
            plan.sesiones, data.fecha_inicio, data.fecha_pago,
        )

    db.commit()
    db.refresh(row)

    if pac.email:
        vigencia_dias = tenant.get_config("vigencia_plan_dias")
        background_tasks.add_task(send_confirmacion_pago, pac.nombre, pac.email, row, vigencia_dias)

    return _out(row, pac.nombre)


@router.delete("/{venta_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venta(
    venta_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Venta, venta_id)
    if not row:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    db.delete(row)
    db.commit()

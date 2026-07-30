import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from database import get_db
from models.gasto import Gasto

METODOS_PAGO = {"Efectivo", "Transferencia", "Tarjeta", "Otro"}

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class GastoCreate(BaseModel):
    nombre:      str
    nit:         str | None = None
    valor:       float
    fecha:       date
    metodo_pago: str
    descripcion: str | None = None

    @field_validator("metodo_pago")
    @classmethod
    def metodo_valido(cls, v: str) -> str:
        if v not in METODOS_PAGO:
            raise ValueError(f"Método de pago inválido. Opciones: {', '.join(METODOS_PAGO)}")
        return v

    @field_validator("valor")
    @classmethod
    def valor_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El valor debe ser mayor a cero.")
        return v


class GastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          str
    nombre:      str
    nit:         str | None
    valor:       float
    fecha:       date
    metodo_pago: str
    descripcion: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[GastoOut])
def list_gastos(
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    q = db.query(Gasto)
    if fecha_desde:
        q = q.filter(Gasto.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(Gasto.fecha <= fecha_hasta)
    return q.order_by(Gasto.fecha.desc()).all()


@router.post("/", response_model=GastoOut, status_code=status.HTTP_201_CREATED)
def create_gasto(
    data: GastoCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = Gasto(
        id=str(uuid.uuid4()),
        nombre=data.nombre,
        nit=data.nit,
        valor=data.valor,
        fecha=data.fecha,
        metodo_pago=data.metodo_pago,
        descripcion=data.descripcion,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{gasto_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gasto(
    gasto_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Gasto, gasto_id)
    if not row:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    db.delete(row)
    db.commit()

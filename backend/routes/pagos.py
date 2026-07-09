import uuid
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from database import get_db
from models.pago import Pago

VIGENCIA_DIAS = 45
TIPOS_VALIDOS = {"Pilates", "Fisioterapia"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class PagoCreate(BaseModel):
    paciente_id:    str
    tipo_paquete:   str
    total_sesiones: int
    fecha_pago:     date

    @field_validator("tipo_paquete")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo_paquete debe ser uno de: {', '.join(TIPOS_VALIDOS)}")
        return v

    @field_validator("total_sesiones")
    @classmethod
    def sesiones_positivas(cls, v: int) -> int:
        if v < 1:
            raise ValueError("total_sesiones debe ser mayor a 0")
        return v


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 str
    paciente_id:        str
    tipo_paquete:       str
    total_sesiones:     int
    sesiones_restantes: int
    fecha_pago:         date
    fecha_vencimiento:  date


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/", response_model=list[PagoOut])
def list_pagos(
    paciente_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    q = db.query(Pago)
    if paciente_id:
        q = q.filter(Pago.paciente_id == paciente_id)
    return q.order_by(Pago.fecha_pago.desc()).all()


@router.post("/", response_model=PagoOut, status_code=status.HTTP_201_CREATED)
def create_pago(
    data: PagoCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = Pago(
        id                 = str(uuid.uuid4()),
        paciente_id        = data.paciente_id,
        tipo_paquete       = data.tipo_paquete,
        total_sesiones     = data.total_sesiones,
        sesiones_restantes = data.total_sesiones,
        fecha_pago         = data.fecha_pago,
        fecha_vencimiento  = data.fecha_pago + timedelta(days=VIGENCIA_DIAS),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{pago_id}", response_model=PagoOut)
def get_pago(
    pago_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Pago, pago_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")
    return row

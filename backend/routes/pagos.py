from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from core.planes import crear_pago
from core.servicios import tipos_validos
from database import current_tenant_id, get_db
from middleware.tenant import get_current_tenant
from models.pago import Pago
from models.tenant import Tenant


# ── Schemas ──────────────────────────────────────────────────────────────────

class PagoCreate(BaseModel):
    paciente_id:    str
    tipo_paquete:   str
    total_sesiones: int
    fecha_pago:     date | None = None
    fecha_inicio:   date

    # tipo_paquete validity depends on the tenant's servicios — checked in
    # create_pago()'s body instead (see routes/citas.py for why).

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
    fecha_pago:         date | None
    fecha_inicio:       date
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
    return q.order_by(Pago.fecha_inicio.desc()).all()


@router.post("/", response_model=PagoOut, status_code=status.HTTP_201_CREATED)
def create_pago(
    data: PagoCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    _: dict = Depends(require_admin),
):
    # Packages are never sold for "Sesión de cortesía" — real servicios only.
    tipos = tipos_validos(db, tenant, incluir_cortesia=False)
    if data.tipo_paquete not in tipos:
        raise HTTPException(
            status_code=422, detail=f"tipo_paquete debe ser uno de: {', '.join(sorted(tipos))}"
        )

    row = crear_pago(
        db, tenant, current_tenant_id.get(), data.paciente_id, data.tipo_paquete,
        data.total_sesiones, data.fecha_inicio, data.fecha_pago,
    )
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

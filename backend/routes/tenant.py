from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.features import features_efectivas
from database import get_db
from models.servicio import Servicio

router = APIRouter()


class ServicioOut(BaseModel):
    nombre: str
    capacidad: int
    duracion_min: int


class TenantConfigOut(BaseModel):
    nombre_comercial: str
    branding: dict
    features: list[str]
    servicios: list[ServicioOut]
    horario: dict
    sesion_cortesia: dict


@router.get("/config", response_model=TenantConfigOut)
def get_tenant_config(request: Request, db: Session = Depends(get_db)):
    """Public (no JWT) — resolved purely from the tenant TenantMiddleware
    already put on request.state. Deliberately never exposes `plan`,
    `estado`, `id`, or `custom_domain` — only what the frontend needs to
    render branding, the nav (via features), and the booking form.

    `sesion_cortesia` tells the frontend whether to offer the courtesy-
    session pseudo-type as a booking option — it has no row in `servicios`
    (see core/servicios.py), so without this the frontend would have no way
    to know it exists for this tenant."""
    tenant = request.state.tenant

    servicios = (
        db.query(Servicio)
        .filter(Servicio.activo == True)  # noqa: E712
        .order_by(Servicio.nombre)
        .all()
    )

    return TenantConfigOut(
        nombre_comercial=tenant.nombre_comercial,
        branding=tenant.branding or {},
        features=sorted(features_efectivas(tenant)),
        servicios=[
            ServicioOut(nombre=s.nombre, capacidad=s.capacidad, duracion_min=s.duracion_min)
            for s in servicios
        ],
        horario=tenant.get_config("horario"),
        sesion_cortesia=tenant.get_config("sesion_cortesia"),
    )

from datetime import time

from sqlalchemy.orm import Session

from models.servicio import Servicio
from models.tenant import Tenant


def capacidad(db: Session, tipo: str) -> int | None:
    """Capacity for a cita 'tipo', read from the tenant's servicios (RLS
    already scopes the query to the current tenant — no explicit tenant_id
    filter needed). "Sesión de cortesía" has no servicio row of its own —
    it reuses the Pilates servicio's capacity, since both occupy the same
    physical class (product decision, see CLAUDE.md)."""
    nombre_servicio = "Pilates" if tipo == "Sesión de cortesía" else tipo
    servicio = (
        db.query(Servicio)
        .filter(Servicio.nombre == nombre_servicio, Servicio.activo == True)  # noqa: E712
        .first()
    )
    return servicio.capacidad if servicio else None


def tipos_validos(db: Session, tenant: Tenant, incluir_cortesia: bool = True) -> set[str]:
    """Valid cita 'tipo' values for this tenant: its active servicios, plus
    the "Sesión de cortesía" pseudo-type when the tenant has it enabled and
    the caller allows it (some flows — médico portal, pagos — never offer
    cortesía, by design, not by omission)."""
    nombres = {s.nombre for s in db.query(Servicio).filter(Servicio.activo == True).all()}  # noqa: E712
    if incluir_cortesia and tenant.get_config("sesion_cortesia.habilitada"):
        nombres.add("Sesión de cortesía")
    return nombres


def hora_valida(tenant: Tenant, hora: time) -> bool:
    """True if `hora` falls on the tenant's slot grid (horario.intervalo_min)
    and inside one of its schedule blocks (horario.bloques)."""
    if hora.second != 0:
        return False
    intervalo = tenant.get_config("horario.intervalo_min")
    if hora.minute % intervalo != 0:
        return False
    for bloque in tenant.get_config("horario.bloques"):
        ini = time.fromisoformat(bloque["inicio"])
        fin = time.fromisoformat(bloque["fin"])
        if ini <= hora <= fin:
            return True
    return False


def descripcion_ventana(tenant: Tenant) -> str:
    """Human-readable schedule window, for error messages — built from the
    tenant's own config instead of a hardcoded "07:00-11:00 · 14:00-18:00"
    string, since that's no longer universally true across tenants."""
    return " · ".join(
        f"{b['inicio']}–{b['fin']}" for b in tenant.get_config("horario.bloques")
    )

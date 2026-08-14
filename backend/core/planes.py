import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.pago import Pago
from models.tenant import Tenant


def plan_disponible(db: Session, paciente_id: str, tipo: str, fecha: date) -> Pago | None:
    """Plan del paciente que cubre `tipo`, sigue vigente en `fecha` y tiene
    sesiones disponibles. Un paciente puede tener varios planes activos a la
    vez (de distinto tipo, o incluso del mismo si renovó antes de vencer) —
    si hay varios que califican, gana el que vence primero (FIFO por
    fecha_vencimiento ascendente), para no dejar sesiones sin usar en un
    plan que está por vencer mientras se consumen las de uno más nuevo.

    "Sesión de cortesía" nunca tiene un Pago propio — los callers que tratan
    ese tipo no deben invocar esta función para él (ver citas.py/portal.py).
    """
    return (
        db.query(Pago)
        .filter(
            Pago.paciente_id == paciente_id,
            Pago.tipo_paquete == tipo,
            Pago.fecha_vencimiento >= fecha,
            Pago.sesiones_restantes > 0,
        )
        .order_by(Pago.fecha_vencimiento.asc())
        .first()
    )


def descontar_sesion(db: Session, paciente_id: str, tipo: str, required: bool = True) -> Pago | None:
    """Descuenta 1 sesión del plan vigente que cubre `tipo` (ver plan_disponible).
    Si `required` y no hay plan con sesiones, levanta 422 — igual comportamiento
    que antes tenía _descuenta_sesion en citas.py."""
    plan = plan_disponible(db, paciente_id, tipo, date.today())
    if not plan:
        if required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El paciente no tiene sesiones disponibles en un plan activo de {tipo}.",
            )
        return None
    plan.sesiones_restantes -= 1
    return plan


def crear_pago(
    db: Session,
    tenant: Tenant,
    tenant_id: str,
    paciente_id: str,
    tipo_paquete: str,
    total_sesiones: int,
    fecha_inicio: date,
    fecha_pago: date | None,
) -> Pago:
    """Crea (sin commitear) un Pago con fecha_vencimiento calculada desde
    fecha_inicio + la vigencia configurada del tenant. Compartido por
    routes/pagos.py (asignación directa) y routes/ventas.py (una Venta con
    sesiones crea su(s) Pago vinculado(s) automáticamente)."""
    vigencia_dias = tenant.get_config("vigencia_plan_dias")
    row = Pago(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        paciente_id=paciente_id,
        tipo_paquete=tipo_paquete,
        total_sesiones=total_sesiones,
        sesiones_restantes=total_sesiones,
        fecha_pago=fecha_pago,
        fecha_inicio=fecha_inicio,
        fecha_vencimiento=fecha_inicio + timedelta(days=vigencia_dias),
    )
    db.add(row)
    return row

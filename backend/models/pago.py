import uuid
from sqlalchemy import Column, Date, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Pago(Base):
    __tablename__ = "pagos"

    id                  = Column(String,  primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id           = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    paciente_id         = Column(String,  nullable=False)
    tipo_paquete        = Column(String,  nullable=False)   # "Pilates" | "Fisioterapia"
    total_sesiones      = Column(Integer, nullable=False)
    sesiones_restantes  = Column(Integer, nullable=False)
    fecha_pago          = Column(Date,    nullable=True)    # null si el plan vino de una Venta "pendiente"
    fecha_inicio        = Column(Date,    nullable=False)   # base for fecha_vencimiento — puede diferir de fecha_pago
    fecha_vencimiento   = Column(Date,    nullable=False)   # computed server-side: fecha_inicio + 45d

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "paciente_id"], ["pacientes.tenant_id", "pacientes.Paciente"],
            name="pagos_tenant_id_paciente_id_fkey",
        ),
    )

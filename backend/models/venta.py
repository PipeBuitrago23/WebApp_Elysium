import uuid
from sqlalchemy import Column, Date, Float, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Venta(Base):
    __tablename__ = "ventas"

    id             = Column(String,  primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id      = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    paciente_id    = Column(String,  nullable=False)
    nombre_paquete = Column(String,  nullable=False)
    categoria      = Column(String,  nullable=False)   # Fisioterapia | Pilates | Combos | Prendas de Vestir
    total_sesiones = Column(Integer, nullable=True)
    valor_total    = Column(Float,   nullable=False)
    abono          = Column(Float,   nullable=False)
    saldo          = Column(Float,   nullable=False)   # valor_total - abono
    fecha_inicio   = Column(Date,    nullable=False)   # base for the linked Pago(s)' fecha_inicio
    fecha_pago     = Column(Date,    nullable=True)     # null while estado == "pendiente"
    metodo_pago    = Column(String,  nullable=False)
    estado         = Column(String,  nullable=False)   # pagada | pendiente

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "paciente_id"], ["pacientes.tenant_id", "pacientes.Paciente"],
            name="ventas_tenant_id_paciente_id_fkey",
        ),
    )

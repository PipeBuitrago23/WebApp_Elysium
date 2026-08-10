import uuid
from sqlalchemy import Boolean, Column, Date, ForeignKey, ForeignKeyConstraint, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Cita(Base):
    __tablename__ = "citas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    paciente_id = Column(String, nullable=False)
    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    tipo = Column(String, nullable=False)
    estado = Column(String, nullable=False, default="programada")
    notas = Column(Text)
    recordatorio_enviado = Column(Boolean, nullable=False, default=False, server_default="false")
    medico_id = Column(String, nullable=True)
    motivo_remision = Column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "paciente_id"], ["pacientes.tenant_id", "pacientes.Paciente"],
            name="citas_tenant_id_paciente_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "medico_id"], ["usuarios.tenant_id", "usuarios.id"],
            name="citas_tenant_id_medico_id_fkey",
        ),
    )

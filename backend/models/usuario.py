import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    # id se mantiene como PK simple (uuid4 propio, colisión entre tenants
    # irreal) — el UNIQUE(tenant_id, id) de abajo solo existe para que
    # citas.medico_id pueda tener una FK compuesta hacia esta tabla.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    es_admin = Column(Boolean, default=False)
    es_medico = Column(Boolean, default=False)
    habeas_data_aceptado = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_aceptacion_habeas = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="usuarios_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "email", name="usuarios_tenant_id_email_key"),
    )

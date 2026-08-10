import uuid
from sqlalchemy import Column, Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Gasto(Base):
    __tablename__ = "gastos"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id   = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    nombre      = Column(String, nullable=False)
    nit         = Column(String, nullable=True)
    valor       = Column(Float,  nullable=False)
    fecha       = Column(Date,   nullable=False)
    metodo_pago = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)

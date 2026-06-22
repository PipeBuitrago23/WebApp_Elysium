import uuid
from sqlalchemy import Column, Date, ForeignKey, Integer, String
from database import Base


class Pago(Base):
    __tablename__ = "pagos"

    id                  = Column(String,  primary_key=True, default=lambda: str(uuid.uuid4()))
    paciente_id         = Column(String,  ForeignKey("pacientes.Paciente"), nullable=False)
    tipo_paquete        = Column(String,  nullable=False)   # "Pilates" | "Fisioterapia"
    total_sesiones      = Column(Integer, nullable=False)
    sesiones_restantes  = Column(Integer, nullable=False)
    fecha_pago          = Column(Date,    nullable=False)
    fecha_vencimiento   = Column(Date,    nullable=False)   # computed server-side: fecha_pago + 45d

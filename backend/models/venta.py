import uuid
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from database import Base


class Venta(Base):
    __tablename__ = "ventas"

    id             = Column(String,  primary_key=True, default=lambda: str(uuid.uuid4()))
    paciente_id    = Column(String,  ForeignKey("pacientes.Paciente"), nullable=False)
    nombre_paquete = Column(String,  nullable=False)
    categoria      = Column(String,  nullable=False)   # Fisioterapia | Pilates | Combos | Prendas de Vestir
    total_sesiones = Column(Integer, nullable=True)
    valor_total    = Column(Float,   nullable=False)
    abono          = Column(Float,   nullable=False)
    saldo          = Column(Float,   nullable=False)   # valor_total - abono
    fecha          = Column(Date,    nullable=False)
    metodo_pago    = Column(String,  nullable=False)
    estado         = Column(String,  nullable=False)   # pagada | pendiente

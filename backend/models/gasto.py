import uuid
from sqlalchemy import Column, Date, Float, String
from database import Base


class Gasto(Base):
    __tablename__ = "gastos"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre      = Column(String, nullable=False)
    nit         = Column(String, nullable=True)
    valor       = Column(Float,  nullable=False)
    fecha       = Column(Date,   nullable=False)
    metodo_pago = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)

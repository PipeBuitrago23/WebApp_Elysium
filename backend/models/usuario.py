import uuid
from sqlalchemy import Boolean, Column, DateTime, String
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    es_admin = Column(Boolean, default=False)
    habeas_data_aceptado = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_aceptacion_habeas = Column(DateTime, nullable=True)

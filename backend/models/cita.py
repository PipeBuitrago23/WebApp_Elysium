import uuid
from sqlalchemy import Boolean, Column, Date, ForeignKey, String, Text, Time
from database import Base


class Cita(Base):
    __tablename__ = "citas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    paciente_id = Column(String, ForeignKey("pacientes.Paciente"), nullable=False)
    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    tipo = Column(String, nullable=False)
    estado = Column(String, nullable=False, default="programada")
    notas = Column(Text)
    recordatorio_enviado = Column(Boolean, nullable=False, default=False, server_default="false")

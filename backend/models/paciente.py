from sqlalchemy import Boolean, Column, Date, DateTime, String, Text
from database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    # Regla de diseño: columna 'Paciente' como PK (no ID_Paciente)
    Paciente = Column(String, primary_key=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String)
    email = Column(String)
    fecha_nacimiento = Column(Date)
    antecedentes = Column(Text)
    cirugias = Column(Text)
    habeas_data_aceptado = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_aceptacion_habeas = Column(DateTime, nullable=True)

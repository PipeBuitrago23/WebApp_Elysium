from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    # PK compuesta (tenant_id, "Paciente") — la cédula ("Paciente", Regla de
    # diseño: nunca renombrar a ID_Paciente) puede repetirse entre tenants.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    Paciente = Column(String, primary_key=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String)
    email = Column(String)
    fecha_nacimiento = Column(Date)
    antecedentes = Column(Text)
    cirugias = Column(Text)
    habeas_data_aceptado = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_aceptacion_habeas = Column(DateTime, nullable=True)

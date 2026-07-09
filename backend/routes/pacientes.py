from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from database import get_db
from models.paciente import Paciente


# ── Schemas ──────────────────────────────────────────────────────────────────

class PacienteCreate(BaseModel):
    Paciente: str
    nombre: str
    telefono: str | None = None
    email: str | None = None
    fecha_nacimiento: date | None = None
    antecedentes: str | None = None
    cirugias: str | None = None


class PacienteUpdate(BaseModel):
    nombre: str | None = None
    telefono: str | None = None
    email: str | None = None
    fecha_nacimiento: date | None = None
    antecedentes: str | None = None
    cirugias: str | None = None


class PacienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Paciente: str
    nombre: str
    telefono: str | None = None
    email: str | None = None
    fecha_nacimiento: date | None = None
    antecedentes: str | None = None
    cirugias: str | None = None


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/", response_model=list[PacienteOut])
def list_pacientes(
    q: str | None = Query(None, description="Busca por nombre, email o teléfono"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    query = db.query(Paciente)
    if q:
        term = f"%{q}%"
        query = query.filter(
            Paciente.nombre.ilike(term)
            | Paciente.email.ilike(term)
            | Paciente.telefono.ilike(term)
        )
    return query.order_by(Paciente.nombre).all()


@router.get("/{paciente_id}", response_model=PacienteOut)
def get_paciente(
    paciente_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Paciente, paciente_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return row


@router.post("/", response_model=PacienteOut, status_code=status.HTTP_201_CREATED)
def create_paciente(
    data: PacienteCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if db.get(Paciente, data.Paciente):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un paciente con ese ID")
    row = Paciente(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{paciente_id}", response_model=PacienteOut)
def update_paciente(
    paciente_id: str,
    data: PacienteUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Paciente, paciente_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{paciente_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paciente(
    paciente_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = db.get(Paciente, paciente_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    db.delete(row)
    db.commit()

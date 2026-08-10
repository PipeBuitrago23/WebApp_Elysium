import uuid
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from auth.jwt import require_admin
from core.constants import MAX_PASSWORD_BYTES
from database import current_tenant_id, get_db
from models.usuario import Usuario


# ── Schemas ──────────────────────────────────────────────────────────────────

class MedicoCreate(BaseModel):
    email: str
    password: str
    nombre: str

    @field_validator("password")
    @classmethod
    def password_valida(cls, v: str) -> str:
        if len(v.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("La contraseña es demasiado larga")
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v


class MedicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre: str


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/", response_model=list[MedicoOut])
def list_medicos(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return (
        db.query(Usuario)
        .filter(Usuario.es_medico == True)  # noqa: E712
        .order_by(Usuario.nombre)
        .all()
    )


@router.post("/", response_model=MedicoOut, status_code=status.HTTP_201_CREATED)
def create_medico(
    data: MedicoCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo")

    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    row = Usuario(
        id=str(uuid.uuid4()),
        tenant_id=current_tenant_id.get(),
        email=data.email,
        hashed_password=hashed,
        nombre=data.nombre,
        es_admin=False,
        es_medico=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

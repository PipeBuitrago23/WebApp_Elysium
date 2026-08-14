import bcrypt
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from auth.jwt import create_access_token, get_current_user
from core.constants import MAX_PASSWORD_BYTES
from database import get_db
from limiter import limiter
from models.paciente import Paciente
from models.usuario import Usuario

router = APIRouter()


class CambiarPasswordBody(BaseModel):
    password_actual: str
    password_nueva: str

    @field_validator("password_nueva")
    @classmethod
    def password_nueva_valida(cls, v: str) -> str:
        if len(v.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("La contraseña es demasiado larga")
        if len(v) < 6:
            raise ValueError("La nueva contraseña debe tener al menos 6 caracteres")
        return v


def verify_password(plain: str, hashed: str) -> bool:
    encoded = plain.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed.encode())


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    tenant_id = request.state.tenant_id
    user = db.query(Usuario).filter(
        Usuario.tenant_id == tenant_id, Usuario.email == form_data.username
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    # For patient accounts, embed their cedula so the portal can auto-load their data
    paciente_id = None
    if not user.es_admin and not user.es_medico:
        pac = db.query(Paciente).filter(
            Paciente.tenant_id == tenant_id, Paciente.email == user.email
        ).first()
        if pac:
            paciente_id = pac.Paciente

    token = create_access_token({
        "sub": user.email,
        "tenant_id": tenant_id,
        "nombre": user.nombre,
        "es_admin": user.es_admin,
        "es_medico": user.es_medico,
        "medico_id": user.id if user.es_medico else None,
        "paciente_id": paciente_id,
        "habeas_data_aceptado": user.habeas_data_aceptado,
    })
    return {"access_token": token, "token_type": "bearer"}


@router.post("/aceptar-habeas")
def aceptar_habeas(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(
        Usuario.tenant_id == current_user["tenant_id"], Usuario.email == current_user["sub"]
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.habeas_data_aceptado = True
    user.fecha_aceptacion_habeas = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/cambiar-password")
def cambiar_password(
    data: CambiarPasswordBody,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(
        Usuario.tenant_id == current_user["tenant_id"], Usuario.email == current_user["sub"]
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not verify_password(data.password_actual, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La contraseña actual es incorrecta")

    user.hashed_password = bcrypt.hashpw(data.password_nueva.encode(), bcrypt.gensalt()).decode()
    db.commit()
    return {"ok": True}

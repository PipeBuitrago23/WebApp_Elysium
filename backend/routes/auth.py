import bcrypt
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from auth.jwt import create_access_token, get_current_user
from database import get_db
from limiter import limiter
from models.paciente import Paciente
from models.usuario import Usuario

router = APIRouter()

_MAX_PASSWORD_BYTES = 72


def verify_password(plain: str, hashed: str) -> bool:
    encoded = plain.encode()
    if len(encoded) > _MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed.encode())


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    # For patient accounts, embed their cedula so the portal can auto-load their data
    paciente_id = None
    if not user.es_admin:
        pac = db.query(Paciente).filter(Paciente.email == user.email).first()
        if pac:
            paciente_id = pac.Paciente

    token = create_access_token({
        "sub": user.email,
        "nombre": user.nombre,
        "es_admin": user.es_admin,
        "paciente_id": paciente_id,
        "habeas_data_aceptado": user.habeas_data_aceptado,
    })
    return {"access_token": token, "token_type": "bearer"}


@router.post("/aceptar-habeas")
def aceptar_habeas(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(Usuario.email == current_user["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.habeas_data_aceptado = True
    user.fecha_aceptacion_habeas = datetime.utcnow()
    db.commit()
    return {"ok": True}

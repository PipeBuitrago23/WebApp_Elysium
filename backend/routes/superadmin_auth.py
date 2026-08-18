from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth.superadmin import create_superadmin_token
from core.constants import MAX_PASSWORD_BYTES
from core.superadmin_db import get_superadmin_db
from limiter import limiter
from models.operador import Operador

router = APIRouter()


def _password_ok(plain: str, hashed: str) -> bool:
    encoded = plain.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed.encode())


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_superadmin_db),
):
    """Superadmin login — separate surface from the tenant /auth/login. Uses the
    superadmin DB connection (DATABASE_URL, bypasses RLS) and returns a token
    signed with the superadmin secret (tipo == "superadmin"). Rate-limited 5/min
    like the tenant login. A generic 401 covers unknown email / wrong password /
    suspended operador alike."""
    email = form_data.username.strip().lower()
    operador = db.query(Operador).filter(Operador.email == email).first()
    if not operador or not operador.activo or not _password_ok(form_data.password, operador.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    operador.ultimo_login = datetime.utcnow()
    db.commit()
    return {"access_token": create_superadmin_token(operador), "token_type": "bearer"}

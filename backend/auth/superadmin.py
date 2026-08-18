import os
import warnings
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from auth.jwt import ALGORITHM, SECRET_KEY
from core.superadmin_db import get_superadmin_db
from models.operador import Operador

# Superadmin tokens are signed with a SEPARATE secret from the tenant JWT
# (JWT_SECRET_KEY): a leak of one must never let an attacker forge tokens of
# the other. This is the highest-privilege surface in the system, and there was
# already a real JWT_SECRET_KEY-in-plaintext leak — the distinct secret isolates
# that blast radius (a tenant-secret leak can't forge a superadmin token, since
# the signature won't verify here). When SUPERADMIN_JWT_SECRET isn't set we fall
# back with a loud warning rather than block the whole app: in prod to
# JWT_SECRET_KEY (degraded — same-secret, still gated by the `tipo` claim), and
# to a dedicated dev constant otherwise. Configure a distinct secret in prod.
_SECRET = os.getenv("SUPERADMIN_JWT_SECRET")
if not _SECRET:
    if os.getenv("JWT_SECRET_KEY"):
        _SECRET = SECRET_KEY
        warnings.warn(
            "SUPERADMIN_JWT_SECRET no configurada — usando JWT_SECRET_KEY como fallback. "
            "Configura un secreto DISTINTO para aislar el blast-radius del superadmin.",
            RuntimeWarning,
            stacklevel=1,
        )
    else:
        _SECRET = "dev-superadmin-secret-change-in-production"

SUPERADMIN_EXPIRE_HOURS = 4  # shorter than a tenant session (8h) — higher privilege

# tokenUrl only drives the OpenAPI "Authorize" box; the real login is the route.
_scheme = OAuth2PasswordBearer(tokenUrl="/superadmin/auth/login")


def create_superadmin_token(operador: Operador) -> str:
    payload = {
        "sub": operador.email,
        "operador_id": str(operador.id),
        "tipo": "superadmin",
        "exp": datetime.utcnow() + timedelta(hours=SUPERADMIN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=ALGORITHM)


def _reject() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_superadmin(
    token: str = Depends(_scheme),
    db: Session = Depends(get_superadmin_db),
) -> Operador:
    """Gate for every /superadmin route except the login itself. Decodes with
    the superadmin secret — a tenant JWT (signed with JWT_SECRET_KEY) fails the
    signature here, so it can never pass; the explicit `tipo` check below is the
    backstop for the degraded same-secret fallback. Re-checks the operador still
    exists and is `activo`, so suspending/deleting an operador immediately
    invalidates its already-issued tokens. Every failure returns the same
    generic 401 — nothing leaks which check failed."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[ALGORITHM])
    except JWTError:
        _reject()
    if payload.get("tipo") != "superadmin":
        _reject()
    operador = db.get(Operador, payload.get("operador_id"))
    if not operador or not operador.activo:
        _reject()
    return operador

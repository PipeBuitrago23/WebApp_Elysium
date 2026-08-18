import os
import warnings
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "dev-secret-key-change-in-production"
    warnings.warn(
        "JWT_SECRET_KEY no configurada — usando clave insegura. Configura esta variable en producción.",
        RuntimeWarning,
        stacklevel=1,
    )

ALGORITHM = "HS256"
EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(hours=EXPIRE_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = verify_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # A superadmin token (tipo == "superadmin", see auth/superadmin.py) must
    # NEVER be accepted by a tenant route, even if it somehow verified — those
    # tokens carry no tenant_id and belong only to the /superadmin surface.
    # (With a distinct SUPERADMIN_JWT_SECRET it wouldn't verify here at all;
    # this is the backstop for the degraded same-secret fallback.) Same generic
    # 401 so nothing leaks which check failed.
    if payload.get("tipo") == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The host resolved by TenantMiddleware is authoritative — the JWT's own
    # tenant_id claim is only ever checked against it, never trusted alone.
    # Same generic message as an invalid signature, so neither response
    # leaks which case actually happened.
    if payload.get("tenant_id") != getattr(request.state, "tenant_id", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("es_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a administradores",
        )
    return current_user


def require_medico(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("es_medico"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a médicos",
        )
    return current_user

import os
import secrets

from fastapi import HTTPException, Header

API_TOKEN_ADMIN = os.getenv("API_TOKEN_ADMIN")
API_TOKEN_READER = os.getenv("API_TOKEN_READER")

def require_read(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.replace("Bearer ", "", 1)

    if secrets.compare_digest(token, API_TOKEN_ADMIN):
        return "admin"

    if secrets.compare_digest(token, API_TOKEN_READER):
        return "reader"

    raise HTTPException(status_code=401, detail="Token invalide")

def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.replace("Bearer ", "", 1)

    if secrets.compare_digest(token, API_TOKEN_ADMIN):
        return "admin"

    raise HTTPException(status_code=403, detail="Accès interdit")
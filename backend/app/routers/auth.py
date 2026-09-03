import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as OrmSession

from .. import models, schemas
from ..database import get_db
from ..auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_HOURS,
    create_session,
    get_current_admin,
)
from ..security import (
    verify_password,
    generate_session_token,
    is_rate_limited,
    record_failed_attempt,
    clear_attempts,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


@router.post("/login", response_model=schemas.MessageOut)
def login(payload: schemas.LoginIn, request: Request, response: Response, db: OrmSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a few minutes and try again.",
        )

    admin = db.query(models.AdminUser).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    clear_attempts(client_ip)

    token = generate_session_token()
    create_session(db, admin.id, token)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return {"message": "Logged in successfully"}


@router.post("/logout", response_model=schemas.MessageOut)
def logout(
    response: Response,
    db: OrmSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if session_token:
        db.query(models.Session).filter(models.Session.token == session_token).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=schemas.MeOut)
def me(admin: models.AdminUser = Depends(get_current_admin)):
    return {"username": admin.username}

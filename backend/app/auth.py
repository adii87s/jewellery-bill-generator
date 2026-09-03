import datetime
import os

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from .database import get_db
from . import models
from .security import hash_password

SESSION_COOKIE_NAME = "session_token"
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "12"))


def ensure_admin_seeded(db: OrmSession) -> None:
    """Create the single admin account on first startup from the
    ADMIN_PASSWORD environment variable, if no admin exists yet.
    Only the hash is ever stored."""
    existing = db.query(models.AdminUser).first()
    if existing:
        return
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        # No admin exists and no seed password provided — the app will
        # simply have no valid login until ADMIN_PASSWORD is set and the
        # server restarted. We do not invent a default password.
        return
    admin = models.AdminUser(username="admin", password_hash=hash_password(admin_password))
    db.add(admin)
    db.commit()


def create_session(db: OrmSession, admin_id: int, token: str) -> models.Session:
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_TTL_HOURS)
    sess = models.Session(token=token, admin_id=admin_id, expires_at=expires)
    db.add(sess)
    db.commit()
    return sess


def get_current_admin(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: OrmSession = Depends(get_db),
) -> models.AdminUser:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    sess = db.query(models.Session).filter(models.Session.token == session_token).first()
    if not sess or sess.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    admin = db.query(models.AdminUser).filter(models.AdminUser.id == sess.admin_id).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return admin

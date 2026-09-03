"""
Database connection / session setup.

DATABASE_URL is read from the environment (see .env.example). It must be a
SQLAlchemy-compatible PostgreSQL URL in production, e.g.:

    postgresql+psycopg2://user:password@host:5432/dbname

For local development without PostgreSQL installed, you may temporarily use
a SQLite URL such as ``sqlite:///./dev.db`` — but do NOT use SQLite in
production; the schema uses PostgreSQL-specific numeric types and the whole
point of this rewrite is durable, concurrent-safe storage.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    # Only relevant for local/dev fallback.
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

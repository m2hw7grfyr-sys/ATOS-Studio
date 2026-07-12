from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import ROOT_DIR, get_settings


class Base(DeclarativeBase):
    pass


def resolve_database_url(database_url: str) -> str:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url
    raw_path = database_url.removeprefix(prefix)
    if raw_path in {":memory:", ""}:
        return database_url
    path = Path(raw_path)
    if path.is_absolute():
        return database_url
    return f"sqlite:///{ROOT_DIR / path}"


def get_database_url() -> str:
    return resolve_database_url(get_settings().studio_database_url)


def connect_args_for(database_url: str) -> dict:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


engine = create_engine(get_database_url(), connect_args=connect_args_for(get_database_url()))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_status() -> str:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return "Connected"
    except Exception:
        return "Unavailable"


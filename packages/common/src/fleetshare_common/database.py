from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fleetshare_common.settings import get_settings


class Base(DeclarativeBase):
    pass


def build_engine():
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError(f"DATABASE_URL is required for service {settings.service_name}")
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


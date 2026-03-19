from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.sql.schema import MetaData

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
logger = logging.getLogger(__name__)


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


def initialize_schema_with_retry(base_metadata: MetaData) -> None:
    settings = get_settings()
    deadline = time.monotonic() + max(settings.db_startup_timeout_seconds, 1)
    last_error: OperationalError | None = None

    while time.monotonic() < deadline:
        try:
            base_metadata.create_all(bind=engine)
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Database for %s is not ready yet; retrying in %ss",
                settings.service_name,
                settings.db_startup_retry_interval_seconds,
            )
            time.sleep(max(settings.db_startup_retry_interval_seconds, 1))

    if last_error is not None:
        raise last_error

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from fleetshare_common.app import create_app
from fleetshare_common.settings import get_settings
from fleetshare_common.timeutils import iso, utcnow_naive

app = create_app("Maintenance Service", "Maintenance ticket wrapper service.")
logger = logging.getLogger("fleetshare.maintenance")


class LocalBase(DeclarativeBase):
    pass


class MaintenanceTicket(LocalBase):
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    damage_severity: Mapped[str] = mapped_column(String(32))
    damage_type: Mapped[str] = mapped_column(String(128))
    recommended_action: Mapped[str] = mapped_column(String(255))
    estimated_duration_hours: Mapped[int] = mapped_column(Integer, default=24)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by_event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class TicketPayload(BaseModel):
    vehicleId: int
    damageSeverity: str
    damageType: str
    recommendedAction: str
    estimatedDurationHours: int = 24
    recordId: int | None = None
    bookingId: int | None = None
    tripId: int | None = None
    openedByEventType: str | None = None
    sourceEventId: str | None = None


_local_engine = None
_local_session_factory = None


def _backend_mode() -> str:
    return get_settings().maintenance_backend_mode.lower()


def _using_outsystems() -> bool:
    return _backend_mode() == "outsystems"


def _backend_header_value() -> str:
    return "outsystems" if _using_outsystems() else "local"


def _set_backend_header(response: Response):
    response.headers["X-Maintenance-Backend"] = _backend_header_value()


def _outsystems_base_url() -> str:
    return get_settings().outsystems_maintenance_base_url.rstrip("/")


def _outsystems_url(path: str) -> str:
    return f"{_outsystems_base_url()}{path}"


def _outsystems_timeout() -> float:
    return float(get_settings().outsystems_maintenance_timeout_seconds)


def _raise_for_status(response: httpx.Response):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc


def _outsystems_request(method: str, path: str, *, payload: dict[str, Any] | None = None) -> Any:
    url = _outsystems_url(path)
    logger.info("maintenance upstream request", extra={"backend": "outsystems", "method": method, "url": url})
    response = httpx.request(method, url, json=payload, timeout=_outsystems_timeout())
    _raise_for_status(response)
    return response.json()


def _normalize_outsystems_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticketId": ticket.get("Id"),
        "vehicleId": ticket.get("vehicle_id"),
        "damageSeverity": ticket.get("damage_severity"),
        "damageType": ticket.get("damage_type"),
        "recommendedAction": ticket.get("recommended_action"),
        "estimatedDurationHours": ticket.get("estimated_duration_hours"),
        "recordId": ticket.get("record_id"),
        "bookingId": ticket.get("booking_id"),
        "tripId": ticket.get("trip_id"),
        "openedByEventType": ticket.get("opened_by_event_type"),
        "sourceEventId": None,
        "status": ticket.get("status"),
        "createdAt": ticket.get("created_at"),
    }


def _serialize_outsystems_payload(payload: TicketPayload) -> dict[str, Any]:
    body = {
        "vehicle_id": payload.vehicleId,
        "damage_severity": payload.damageSeverity,
        "damage_type": payload.damageType,
        "recommended_action": payload.recommendedAction,
        "estimated_duration_hours": payload.estimatedDurationHours,
        "status": "OPEN",
        "opened_by_event_type": payload.openedByEventType,
    }
    if payload.recordId is not None:
        body["record_id"] = payload.recordId
    if payload.bookingId is not None:
        body["booking_id"] = payload.bookingId
    if payload.tripId is not None:
        body["trip_id"] = payload.tripId
    return body


def _build_local_engine():
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required when maintenance backend mode is local")
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def _initialize_local_backend():
    global _local_engine, _local_session_factory
    if _local_engine is not None and _local_session_factory is not None:
        return
    _local_engine = _build_local_engine()
    _local_session_factory = sessionmaker(bind=_local_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    _initialize_local_schema_with_retry()
    ensure_source_event_id_column()


def _initialize_local_schema_with_retry():
    settings = get_settings()
    deadline = time.monotonic() + max(settings.db_startup_timeout_seconds, 1)
    last_error: OperationalError | None = None

    while time.monotonic() < deadline:
        try:
            LocalBase.metadata.create_all(bind=_local_engine)
            return
        except OperationalError as exc:  # pragma: no cover - startup retry
            last_error = exc
            logger.warning(
                "Database for %s is not ready yet; retrying in %ss",
                settings.service_name,
                settings.db_startup_retry_interval_seconds,
            )
            time.sleep(max(settings.db_startup_retry_interval_seconds, 1))

    if last_error is not None:
        raise last_error


@contextmanager
def _local_session_scope():
    _initialize_local_backend()
    session = _local_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_source_event_id_column():
    if _local_engine is None:
        raise RuntimeError("Local maintenance backend is not initialized")
    with _local_engine.begin() as connection:
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("maintenance_tickets")}
        if "source_event_id" not in columns:
            connection.execute(text("ALTER TABLE maintenance_tickets ADD COLUMN source_event_id VARCHAR(64) NULL"))
        indexes = {index["name"] for index in inspector.get_indexes("maintenance_tickets")}
        if "ix_maintenance_tickets_source_event_id" not in indexes:
            connection.execute(
                text("CREATE UNIQUE INDEX ix_maintenance_tickets_source_event_id ON maintenance_tickets (source_event_id)")
            )


def _ticket_to_dict(ticket: MaintenanceTicket) -> dict[str, Any]:
    return {
        "ticketId": ticket.id,
        "vehicleId": ticket.vehicle_id,
        "damageSeverity": ticket.damage_severity,
        "damageType": ticket.damage_type,
        "recommendedAction": ticket.recommended_action,
        "estimatedDurationHours": ticket.estimated_duration_hours,
        "recordId": ticket.record_id,
        "bookingId": ticket.booking_id,
        "tripId": ticket.trip_id,
        "openedByEventType": ticket.opened_by_event_type,
        "sourceEventId": ticket.source_event_id,
        "status": ticket.status,
        "createdAt": iso(ticket.created_at),
    }


def _filter_tickets(
    tickets: list[dict[str, Any]],
    *,
    vehicle_id: int | None = None,
    damage_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    filtered = tickets
    if vehicle_id is not None:
        filtered = [ticket for ticket in filtered if ticket.get("vehicleId") == vehicle_id]
    if damage_type:
        normalized_filter = str(damage_type).strip().lower()
        filtered = [ticket for ticket in filtered if str(ticket.get("damageType", "")).strip().lower() == normalized_filter]
    if status:
        normalized_status = str(status).strip().upper()
        filtered = [ticket for ticket in filtered if str(ticket.get("status", "")).strip().upper() == normalized_status]
    return filtered


def _list_local_tickets(
    *,
    vehicle_id: int | None = None,
    damage_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with _local_session_scope() as db:
        tickets = db.query(MaintenanceTicket).order_by(MaintenanceTicket.id.desc()).all()
        return _filter_tickets(
            [_ticket_to_dict(ticket) for ticket in tickets],
            vehicle_id=vehicle_id,
            damage_type=damage_type,
            status=status,
        )


def _create_local_ticket(payload: TicketPayload) -> dict[str, Any]:
    with _local_session_scope() as db:
        if payload.sourceEventId:
            existing = (
                db.query(MaintenanceTicket)
                .filter(MaintenanceTicket.source_event_id == payload.sourceEventId)
                .order_by(MaintenanceTicket.id.desc())
                .first()
            )
            if existing:
                return _ticket_to_dict(existing)
        ticket = MaintenanceTicket(
            vehicle_id=payload.vehicleId,
            damage_severity=payload.damageSeverity,
            damage_type=payload.damageType,
            recommended_action=payload.recommendedAction,
            estimated_duration_hours=payload.estimatedDurationHours,
            record_id=payload.recordId,
            booking_id=payload.bookingId,
            trip_id=payload.tripId,
            opened_by_event_type=payload.openedByEventType,
            source_event_id=payload.sourceEventId,
        )
        db.add(ticket)
        db.flush()
        db.refresh(ticket)
        return _ticket_to_dict(ticket)


def _get_local_ticket(ticket_id: int) -> dict[str, Any]:
    with _local_session_scope() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return _ticket_to_dict(ticket)


@app.on_event("startup")
def startup_event():
    if not _using_outsystems():
        _initialize_local_backend()


@app.get("/maintenance/backend-info")
def maintenance_backend_info(response: Response):
    _set_backend_header(response)
    return {
        "backendMode": _backend_mode(),
        "backend": _backend_header_value(),
        "outsystemsBaseUrl": _outsystems_base_url(),
    }


@app.get("/maintenance/tickets")
def list_tickets(
    response: Response,
    vehicleId: int | None = None,
    damageType: str | None = None,
    status: str | None = None,
):
    _set_backend_header(response)
    if _using_outsystems():
        tickets = _outsystems_request("GET", "/tickets")
        return _filter_tickets(
            [_normalize_outsystems_ticket(ticket) for ticket in tickets],
            vehicle_id=vehicleId,
            damage_type=damageType,
            status=status,
        )
    return _list_local_tickets(vehicle_id=vehicleId, damage_type=damageType, status=status)


@app.post("/maintenance/tickets")
def create_ticket(payload: TicketPayload, response: Response):
    _set_backend_header(response)
    if _using_outsystems():
        ticket = _outsystems_request("POST", "/tickets", payload=_serialize_outsystems_payload(payload))
        return _normalize_outsystems_ticket(ticket)
    return _create_local_ticket(payload)


@app.get("/maintenance/tickets/{ticket_id}")
def get_ticket(ticket_id: int, response: Response):
    _set_backend_header(response)
    if _using_outsystems():
        ticket = _outsystems_request("GET", f"/tickets/{ticket_id}")
        return _normalize_outsystems_ticket(ticket)
    return _get_local_ticket(ticket_id)

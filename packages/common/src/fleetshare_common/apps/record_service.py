from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry

app = create_app("Record Service", "Atomic evidence and record management service.")


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    record_type: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="MODERATE")
    review_state: Mapped[str] = mapped_column(String(64), default="PENDING_EXTERNAL")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_urls: Mapped[list] = mapped_column(JSON, default=list)
    detected_damage: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RecordPayload(BaseModel):
    bookingId: int | None = None
    tripId: int | None = None
    vehicleId: int
    recordType: str
    notes: str | None = None
    severity: str = "MODERATE"
    reviewState: str = "PENDING_EXTERNAL"
    confidence: float = 0.0
    evidenceUrls: list[str] = Field(default_factory=list)
    detectedDamage: list[str] = Field(default_factory=list)


class RecordPatchPayload(BaseModel):
    severity: str | None = None
    reviewState: str | None = None
    confidence: float | None = None
    detectedDamage: list[str] | None = None


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)


def record_to_dict(record: Record) -> dict:
    return {
        "recordId": record.id,
        "bookingId": record.booking_id,
        "tripId": record.trip_id,
        "vehicleId": record.vehicle_id,
        "recordType": record.record_type,
        "notes": record.notes,
        "severity": record.severity,
        "reviewState": record.review_state,
        "confidence": record.confidence,
        "evidenceUrls": record.evidence_urls,
        "detectedDamage": record.detected_damage,
        "createdAt": record.created_at.isoformat() if record.created_at else None,
        "updatedAt": record.updated_at.isoformat() if record.updated_at else None,
    }


@app.get("/records")
def list_records(
    bookingId: int | None = None,
    tripId: int | None = None,
    vehicleId: int | None = None,
    recordType: str | None = None,
    reviewState: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Record)
    if bookingId is not None:
        query = query.filter(Record.booking_id == bookingId)
    if tripId is not None:
        query = query.filter(Record.trip_id == tripId)
    if vehicleId is not None:
        query = query.filter(Record.vehicle_id == vehicleId)
    if recordType is not None:
        query = query.filter(Record.record_type == recordType)
    if reviewState is not None:
        query = query.filter(Record.review_state == reviewState)
    return [record_to_dict(record) for record in query.order_by(Record.id.desc()).all()]


@app.post("/records")
def create_record(payload: RecordPayload, db: Session = Depends(get_db)):
    record = Record(
        booking_id=payload.bookingId,
        trip_id=payload.tripId,
        vehicle_id=payload.vehicleId,
        record_type=payload.recordType,
        notes=payload.notes,
        severity=payload.severity,
        review_state=payload.reviewState,
        confidence=payload.confidence,
        evidence_urls=payload.evidenceUrls,
        detected_damage=payload.detectedDamage,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"recordId": record.id, "status": record.review_state}


@app.patch("/records/{record_id}")
def patch_record(record_id: int, payload: RecordPatchPayload, db: Session = Depends(get_db)):
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if payload.severity is not None:
        record.severity = payload.severity
    if payload.reviewState is not None:
        record.review_state = payload.reviewState
    if payload.confidence is not None:
        record.confidence = payload.confidence
    if payload.detectedDamage is not None:
        record.detected_damage = payload.detectedDamage
    db.commit()
    return {"recordId": record.id, "status": record.review_state}


@app.get("/records/manual-review-queue")
def manual_review_queue(db: Session = Depends(get_db)):
    records = db.query(Record).filter(Record.review_state == "MANUAL_REVIEW").order_by(Record.id.desc()).all()
    return [record_to_dict(record) for record in records]

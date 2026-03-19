from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.contracts import TripStatus
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry
from fleetshare_common.messaging import publish_event
from fleetshare_common.pricing import post_midnight_hours
from fleetshare_common.timeutils import as_utc_naive, iso, utcnow

app = create_app("Trip Service", "Atomic trip lifecycle service.")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default=TripStatus.PENDING.value)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    disruption_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subscription_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_hours: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TripStartPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str
    startedAt: datetime | None = None
    subscriptionSnapshot: dict = Field(default_factory=dict)


class TripStatusPayload(BaseModel):
    status: str
    endedAt: datetime | None = None
    endReason: str | None = None
    disruptionReason: str | None = None


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)


def trip_to_dict(trip: Trip) -> dict:
    return {
        "tripId": trip.id,
        "bookingId": trip.booking_id,
        "vehicleId": trip.vehicle_id,
        "userId": trip.user_id,
        "status": trip.status,
        "startedAt": iso(trip.started_at),
        "endedAt": iso(trip.ended_at),
        "endReason": trip.end_reason,
        "disruptionReason": trip.disruption_reason,
        "durationHours": round(trip.duration_hours, 2),
        "subscriptionSnapshot": trip.subscription_snapshot,
    }


@app.get("/trips")
def list_trips(userId: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Trip)
    if userId:
        query = query.filter(Trip.user_id == userId)
    return [trip_to_dict(trip) for trip in query.order_by(Trip.id.desc()).all()]


@app.get("/trips/{trip_id}")
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip_to_dict(trip)


@app.post("/trips/start")
def create_trip(payload: TripStartPayload, db: Session = Depends(get_db)):
    started_at = as_utc_naive(payload.startedAt or utcnow())
    trip = Trip(
        booking_id=payload.bookingId,
        vehicle_id=payload.vehicleId,
        user_id=payload.userId,
        started_at=started_at,
        status=TripStatus.STARTED.value,
        subscription_snapshot=payload.subscriptionSnapshot,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return {"tripId": trip.id, "status": trip.status}


@app.patch("/trips/{trip_id}/status")
def patch_trip_status(trip_id: int, payload: TripStatusPayload, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.status == TripStatus.ENDED.value and payload.status == TripStatus.ENDED.value:
        return {"tripId": trip.id, "status": trip.status, "idempotent": True}
    trip.status = payload.status
    if payload.status == TripStatus.ENDED.value:
        trip.ended_at = as_utc_naive(payload.endedAt or utcnow())
        trip.end_reason = payload.endReason
        trip.disruption_reason = payload.disruptionReason
        trip.duration_hours = max((trip.ended_at - trip.started_at).total_seconds() / 3600.0, 0.0)
        db.commit()
        publish_event(
            "trip.ended",
            {
                "tripId": trip.id,
                "bookingId": trip.booking_id,
                "vehicleId": trip.vehicle_id,
                "userId": trip.user_id,
                "tripStartTime": iso(trip.started_at),
                "tripEndTime": iso(trip.ended_at),
                "durationHours": round(trip.duration_hours, 2),
            },
        )
    else:
        db.commit()
    return {"tripId": trip.id, "status": trip.status}


@app.get("/trips/{trip_id}/post-midnight-usage")
def get_post_midnight_usage(trip_id: int, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip or not trip.ended_at:
        raise HTTPException(status_code=404, detail="Completed trip not found")
    usage = post_midnight_hours(trip.started_at, trip.ended_at)
    return {
        "tripId": trip.id,
        "actualPostMidnightHours": round(usage, 2),
        "tripStartTime": iso(trip.started_at),
        "tripEndTime": iso(trip.ended_at),
        "tripUsageSummary": f"{round(usage, 2)} hours after midnight",
    }

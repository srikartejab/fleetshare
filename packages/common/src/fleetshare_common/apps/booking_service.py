from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.contracts import BookingStatus
from fleetshare_common.database import Base, engine, get_db
from fleetshare_common.timeutils import as_utc_naive, iso

app = create_app("Booking Service", "Atomic booking reservation service.")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    pickup_location: Mapped[str] = mapped_column(String(128))
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    displayed_price: Mapped[float] = mapped_column(Float)
    final_price: Mapped[float] = mapped_column(Float, default=0.0)
    subscription_plan_id: Mapped[str] = mapped_column(String(64), default="STANDARD_MONTHLY")
    status: Mapped[str] = mapped_column(String(64), default=BookingStatus.PAYMENT_PENDING.value)
    cross_cycle_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    refund_pending_on_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_status: Mapped[str] = mapped_column(String(64), default="PENDING")
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class VehicleReservationLock(Base):
    __tablename__ = "vehicle_reservation_locks"

    vehicle_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class BookingCreatePayload(BaseModel):
    userId: str
    vehicleId: int
    pickupLocation: str
    startTime: datetime
    endTime: datetime
    displayedPrice: float
    subscriptionPlanId: str = "STANDARD_MONTHLY"
    crossCycleBooking: bool = False
    refundPendingOnRenewal: bool = False
    bookingNote: str | None = None
    pricingSnapshot: dict = Field(default_factory=dict)


class BookingStatusPayload(BaseModel):
    status: str
    tripId: int | None = None
    cancellationReason: str | None = None


class ReconciliationPayload(BaseModel):
    refund_pending_on_renewal: bool
    reconciliationStatus: str


class BookingFinancialsPayload(BaseModel):
    finalPrice: float


class CancelAffectedPayload(BaseModel):
    vehicleId: int
    estimatedDurationHours: int
    reason: str = "VEHICLE_UNAVAILABLE"


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


def booking_to_dict(booking: Booking) -> dict:
    return {
        "bookingId": booking.id,
        "userId": booking.user_id,
        "vehicleId": booking.vehicle_id,
        "pickupLocation": booking.pickup_location,
        "startTime": iso(booking.start_time),
        "endTime": iso(booking.end_time),
        "status": booking.status,
        "displayedPrice": booking.displayed_price,
        "finalPrice": booking.final_price,
        "crossCycleBooking": booking.cross_cycle_booking,
        "refundPendingOnRenewal": booking.refund_pending_on_renewal,
        "reconciliationStatus": booking.reconciliation_status,
        "tripId": booking.trip_id,
        "bookingNote": booking.booking_note,
        "cancellationReason": booking.cancellation_reason,
        "pricingSnapshot": booking.metadata_json or {},
    }


@app.get("/bookings")
def list_bookings(userId: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Booking)
    if userId:
        query = query.filter(Booking.user_id == userId)
    return [booking_to_dict(booking) for booking in query.order_by(Booking.id.desc()).all()]


@app.get("/booking/{booking_id}")
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking_to_dict(booking)


@app.get("/bookings/availability")
def booking_availability(
    vehicleId: int | None = None,
    vehicleIds: str | None = None,
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    db: Session = Depends(get_db),
):
    normalized_start = as_utc_naive(startTime)
    normalized_end = as_utc_naive(endTime)
    requested_ids = []
    if vehicleId:
        requested_ids = [vehicleId]
    elif vehicleIds:
        requested_ids = [int(item) for item in vehicleIds.split(",") if item]
    if not requested_ids:
        raise HTTPException(status_code=400, detail="vehicleId or vehicleIds is required")

    available = []
    for requested_id in requested_ids:
        conflicting = (
            db.query(Booking)
            .filter(
                Booking.vehicle_id == requested_id,
                Booking.status.in_([BookingStatus.PAYMENT_PENDING.value, BookingStatus.CONFIRMED.value]),
                Booking.start_time < normalized_end,
                Booking.end_time > normalized_start,
            )
            .count()
        )
        if conflicting == 0:
            available.append(requested_id)
    return {"slotAvailable": bool(available) if vehicleId else None, "availableVehicleIds": available}


@app.get("/bookings/reconciliation-pending")
def reconciliation_pending(userId: str, billingCycleId: str | None = None, db: Session = Depends(get_db)):
    bookings = db.query(Booking).filter(Booking.user_id == userId, Booking.refund_pending_on_renewal.is_(True)).all()
    return {
        "bookingIds": [booking.id for booking in bookings],
        "tripIds": [booking.trip_id for booking in bookings if booking.trip_id is not None],
        "reconciliationCandidates": [booking_to_dict(booking) for booking in bookings],
        "billingCycleId": billingCycleId,
    }


@app.post("/booking")
def create_booking(payload: BookingCreatePayload, db: Session = Depends(get_db)):
    normalized_start = as_utc_naive(payload.startTime)
    normalized_end = as_utc_naive(payload.endTime)
    lock = db.get(VehicleReservationLock, payload.vehicleId)
    if not lock:
        db.add(VehicleReservationLock(vehicle_id=payload.vehicleId))
        db.commit()
    db.query(VehicleReservationLock).filter(VehicleReservationLock.vehicle_id == payload.vehicleId).with_for_update().first()

    conflict = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == payload.vehicleId,
            Booking.status.in_([BookingStatus.PAYMENT_PENDING.value, BookingStatus.CONFIRMED.value]),
            Booking.start_time < normalized_end,
            Booking.end_time > normalized_start,
        )
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Vehicle slot is already reserved")

    booking = Booking(
        user_id=payload.userId,
        vehicle_id=payload.vehicleId,
        pickup_location=payload.pickupLocation,
        start_time=normalized_start,
        end_time=normalized_end,
        displayed_price=payload.displayedPrice,
        final_price=payload.displayedPrice,
        subscription_plan_id=payload.subscriptionPlanId,
        cross_cycle_booking=payload.crossCycleBooking,
        refund_pending_on_renewal=payload.refundPendingOnRenewal,
        booking_note=payload.bookingNote,
        metadata_json=payload.pricingSnapshot,
        status=BookingStatus.PAYMENT_PENDING.value,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"bookingId": booking.id, "status": booking.status}


@app.patch("/booking/{booking_id}/status")
def patch_booking_status(booking_id: int, payload: BookingStatusPayload, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = payload.status
    if payload.tripId is not None:
        booking.trip_id = payload.tripId
    if payload.cancellationReason:
        booking.cancellation_reason = payload.cancellationReason
    db.commit()
    return {"bookingId": booking.id, "status": booking.status}


@app.patch("/booking/{booking_id}/financials")
def patch_booking_financials(booking_id: int, payload: BookingFinancialsPayload, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.final_price = payload.finalPrice
    db.commit()
    return {"bookingId": booking.id, "finalPrice": booking.final_price}


@app.patch("/booking/{booking_id}/reconciliation-status")
def patch_reconciliation_status(booking_id: int, payload: ReconciliationPayload, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.refund_pending_on_renewal = payload.refund_pending_on_renewal
    booking.reconciliation_status = payload.reconciliationStatus
    if payload.reconciliationStatus == "COMPLETED":
        booking.status = BookingStatus.RECONCILED.value
    db.commit()
    return {"reconciliationStatus": booking.reconciliation_status}


@app.put("/bookings/cancel-affected")
def cancel_affected(payload: CancelAffectedPayload, db: Session = Depends(get_db)):
    bookings = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == payload.vehicleId,
            Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.PAYMENT_PENDING.value]),
        )
        .all()
    )
    affected_ids = []
    for booking in bookings:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancellation_reason = payload.reason
        affected_ids.append(booking.id)
    db.commit()
    return {"affectedBookingIds": affected_ids, "cancelledCount": len(affected_ids)}

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class VehicleStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    IN_USE = "IN_USE"
    UNDER_INSPECTION = "UNDER_INSPECTION"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"


class BookingStatus(StrEnum):
    PAYMENT_PENDING = "PAYMENT_PENDING"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DISRUPTED = "DISRUPTED"
    RECONCILED = "RECONCILED"


class TripStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    ENDED = "ENDED"
    BLOCKED = "BLOCKED"


class RecordSeverity(StrEnum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class ReviewState(StrEnum):
    PENDING_EXTERNAL = "PENDING_EXTERNAL"
    EXTERNAL_ASSESSED = "EXTERNAL_ASSESSED"
    EXTERNAL_BLOCKED = "EXTERNAL_BLOCKED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    RESOLVED = "RESOLVED"


class PaymentStatus(StrEnum):
    REQUIRED = "REQUIRED"
    SUCCESS = "SUCCESS"
    REFUNDED = "REFUNDED"
    ADJUSTED = "ADJUSTED"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    OPS = "OPS"


class TelemetrySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SearchVehiclesResponse(BaseModel):
    vehicleList: list[dict[str, Any]]
    estimatedPrice: float
    availabilitySummary: str


class BookingCreateRequest(BaseModel):
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


class PaymentRequest(BaseModel):
    bookingId: int
    userId: str
    amount: float
    reason: str
    currency: str = "SGD"


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any]


class ApiMessage(BaseModel):
    message: str


from __future__ import annotations

import threading
from concurrent import futures
from datetime import datetime

import grpc
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.contracts import VehicleStatus
from fleetshare_common.database import Base, SessionLocal, get_db, initialize_schema_with_retry
from fleetshare_common.generated import vehicle_pb2, vehicle_pb2_grpc
from fleetshare_common.messaging import publish_event
from fleetshare_common.station_catalog import STATION_CATALOG, get_station
from fleetshare_common.timeutils import iso, utcnow_naive

app = create_app("Vehicle Service", "Atomic vehicle state and telemetry service.")


OPERATIONALLY_ELIGIBLE_STATUSES = {
    VehicleStatus.AVAILABLE.value,
    VehicleStatus.BOOKED.value,
    VehicleStatus.IN_USE.value,
}


LOCK_PRESERVED_STATUSES = {
    VehicleStatus.MAINTENANCE_REQUIRED.value,
    VehicleStatus.UNDER_INSPECTION.value,
}


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True)
    model: Mapped[str] = mapped_column(String(128))
    zone: Mapped[str] = mapped_column(String(64))
    vehicle_type: Mapped[str] = mapped_column(String(64), default="SEDAN")
    status: Mapped[str] = mapped_column(String(64), default=VehicleStatus.AVAILABLE.value)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class TelemetrySnapshot(Base):
    __tablename__ = "telemetry_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    battery_level: Mapped[int] = mapped_column(Integer, default=100)
    tire_pressure_ok: Mapped[str] = mapped_column(String(16), default="true")
    severity: Mapped[str] = mapped_column(String(32), default="INFO")
    fault_code: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class VehicleStatusPayload(BaseModel):
    status: VehicleStatus


class TelemetryPayload(BaseModel):
    vehicleId: int
    batteryLevel: int = 100
    tirePressureOk: bool = True
    severity: str = "INFO"
    faultCode: str = ""


def telemetry_requires_attention(*, battery_level: int, tire_pressure_ok: bool, severity: str, fault_code: str) -> bool:
    return severity in {"WARNING", "CRITICAL"} or battery_level < 20 or not tire_pressure_ok or bool(fault_code)


def serialize_vehicle(vehicle: Vehicle) -> dict:
    station = get_station(vehicle.zone)
    return {
        "id": vehicle.id,
        "vehicleId": vehicle.id,
        "plateNumber": vehicle.plate_number,
        "model": vehicle.model,
        "zone": vehicle.zone,
        "vehicleType": vehicle.vehicle_type,
        "status": vehicle.status,
        "stationId": station["id"],
        "stationName": station["name"],
        "stationAddress": station["address"],
        "area": station["area"],
        "latitude": station["latitude"],
        "longitude": station["longitude"],
    }


def is_operationally_eligible(vehicle: Vehicle) -> bool:
    """Return whether the vehicle may be considered for future bookings.

    Operational eligibility is intentionally separate from requested time-slot
    availability. Vehicles that are currently BOOKED or IN_USE may still be
    bookable for a later slot; blocked administrative states remain ineligible.
    """

    return vehicle.status in OPERATIONALLY_ELIGIBLE_STATUSES


def seed_data():
    with SessionLocal() as db:
        existing_vehicle_ids = {vehicle_id for (vehicle_id,) in db.query(Vehicle.id).all()}
        vehicles = [
            Vehicle(id=1, plate_number="SFA1001A", model="Tesla Model 3", zone="SMU", vehicle_type="SEDAN"),
            Vehicle(id=2, plate_number="SFA1002B", model="BYD Atto 3", zone="SMU", vehicle_type="SUV"),
            Vehicle(id=3, plate_number="SFA1003C", model="Hyundai Kona", zone="TAMPINES", vehicle_type="SUV"),
            Vehicle(id=4, plate_number="SFA1004D", model="BMW i3", zone="SMU", vehicle_type="COMPACT"),
            Vehicle(id=5, plate_number="SFA2005E", model="Volvo XC40", zone="CHANGI", vehicle_type="SUV"),
            Vehicle(id=6, plate_number="SFA2006F", model="Mercedes EQE", zone="ORCHARD", vehicle_type="LUXURY"),
            Vehicle(id=7, plate_number="SFA2007G", model="Kia EV6", zone="TAMPINES", vehicle_type="SEDAN"),
            Vehicle(id=8, plate_number="SFA2008H", model="Hyundai Staria", zone="WOODLANDS", vehicle_type="MPV"),
            Vehicle(id=101, plate_number="EVA1101K", model="MG 4 EV", zone="PASIR_RIS_BLK_149A", vehicle_type="SEDAN"),
            Vehicle(id=102, plate_number="EVA1102L", model="BYD Dolphin", zone="PASIR_RIS_BLK_149A", vehicle_type="COMPACT"),
            Vehicle(id=103, plate_number="EVA1103M", model="Hyundai Kona Electric", zone="PASIR_RIS_BLK_152", vehicle_type="SUV"),
            Vehicle(id=104, plate_number="EVA1104N", model="Ora Good Cat", zone="PASIR_RIS_ST_11", vehicle_type="COMPACT"),
            Vehicle(id=105, plate_number="EVA1105P", model="Kia Niro EV", zone="PASIR_RIS_ST_11", vehicle_type="SUV"),
            Vehicle(id=106, plate_number="EVA1106Q", model="BYD Seal", zone="LOYANG_AVE", vehicle_type="SEDAN"),
            Vehicle(id=107, plate_number="EVA1107R", model="Volvo EX30", zone="LOYANG_AVE", vehicle_type="SUV"),
            Vehicle(id=108, plate_number="EVA1108S", model="Peugeot e-2008", zone="FLORA_DR", vehicle_type="SUV", status=VehicleStatus.BOOKED.value),
            Vehicle(id=109, plate_number="EVA1109T", model="Opel Mokka-e", zone="FLORA_DR", vehicle_type="COMPACT"),
            Vehicle(id=110, plate_number="EVA1110U", model="MG 5 EV", zone="TAMPINES_ST_45", vehicle_type="SEDAN", status=VehicleStatus.MAINTENANCE_REQUIRED.value),
            Vehicle(id=111, plate_number="EVA1111V", model="Nissan Leaf", zone="TAMPINES_ST_34", vehicle_type="COMPACT"),
            Vehicle(id=112, plate_number="EVA1112W", model="Citroen e-C4", zone="TAMPINES_ST_34", vehicle_type="SEDAN"),
            Vehicle(id=113, plate_number="EVA1113X", model="BYD Atto 3", zone="CHANGI", vehicle_type="SUV"),
            Vehicle(id=114, plate_number="EVA1114Y", model="Tesla Model Y", zone="SMU", vehicle_type="SUV"),
            Vehicle(id=115, plate_number="EVA1115Z", model="BMW iX1", zone="ORCHARD", vehicle_type="SUV"),
            Vehicle(id=116, plate_number="EVB1116A", model="Hyundai Ioniq 5", zone="PASIR_RIS_BLK_152", vehicle_type="SUV"),
            Vehicle(id=117, plate_number="EVB1117B", model="Kia EV6", zone="PASIR_RIS_BLK_149A", vehicle_type="SEDAN"),
            Vehicle(id=118, plate_number="EVB1118C", model="Hyundai Kona Electric", zone="LOYANG_AVE", vehicle_type="SUV"),
        ]
        for vehicle in vehicles:
            if vehicle.id in existing_vehicle_ids:
                continue
            db.add(vehicle)
        db.commit()

        for vehicle in vehicles:
            latest_snapshot = (
                db.query(TelemetrySnapshot)
                .filter(TelemetrySnapshot.vehicle_id == vehicle.id)
                .order_by(TelemetrySnapshot.created_at.desc(), TelemetrySnapshot.id.desc())
                .first()
            )
            if (
                latest_snapshot
                and latest_snapshot.battery_level >= 88
                and latest_snapshot.tire_pressure_ok == "true"
                and latest_snapshot.severity == "INFO"
                and not latest_snapshot.fault_code
            ):
                continue
            db.add(
                TelemetrySnapshot(
                    vehicle_id=vehicle.id,
                    battery_level=88,
                    tire_pressure_ok="true",
                    severity="INFO",
                    fault_code="",
                )
            )
        db.commit()


def get_vehicle_or_404(db: Session, vehicle_id: int) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)
    seed_data()
    threading.Thread(target=start_grpc_server, daemon=True).start()


@app.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    return [serialize_vehicle(vehicle) for vehicle in db.query(Vehicle).order_by(Vehicle.id).all()]


@app.get("/vehicles/filters")
def list_vehicle_filters(db: Session = Depends(get_db)):
    vehicles = db.query(Vehicle).order_by(Vehicle.id.asc()).all()
    location_ids = {vehicle.zone for vehicle in vehicles}
    locations = [station["id"] for station in STATION_CATALOG if station["id"] in location_ids]
    locations.extend(sorted(location_id for location_id in location_ids if location_id not in locations))
    vehicle_types = sorted({vehicle.vehicle_type for vehicle in vehicles})
    return {
        "locations": locations,
        "vehicleTypes": vehicle_types,
        "locationOptions": [
            {
                "id": station["id"],
                "label": station["name"],
                "address": station["address"],
                "area": station["area"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
            }
            for station in (get_station(location_id) for location_id in locations)
        ],
    }


@app.get("/vehicles/stations")
def list_vehicle_stations(db: Session = Depends(get_db)):
    vehicles = db.query(Vehicle).order_by(Vehicle.id.asc()).all()
    counts: dict[str, dict[str, int]] = {}
    for vehicle in vehicles:
        bucket = counts.setdefault(vehicle.zone, {"totalVehicleCount": 0, "operationalAvailableCount": 0})
        bucket["totalVehicleCount"] += 1
        if vehicle.status == VehicleStatus.AVAILABLE.value:
            bucket["operationalAvailableCount"] += 1

    stations = []
    known_ids = {vehicle.zone for vehicle in vehicles}
    ordered_ids = [station["id"] for station in STATION_CATALOG if station["id"] in known_ids]
    ordered_ids.extend(sorted(station_id for station_id in known_ids if station_id not in ordered_ids))
    for station_id in ordered_ids:
        station = get_station(station_id)
        bucket = counts.get(station_id, {"totalVehicleCount": 0, "operationalAvailableCount": 0})
        stations.append(
            {
                "stationId": station["id"],
                "stationName": station["name"],
                "stationAddress": station["address"],
                "area": station["area"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "totalVehicleCount": bucket["totalVehicleCount"],
                "operationalAvailableCount": bucket["operationalAvailableCount"],
                "nextAvailableTiming": station["nextAvailableTiming"],
            }
        )
    return stations


@app.get("/vehicles/availability")
def get_vehicle_availability(zone: str | None = None, stationId: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Vehicle)
    lookup_zone = stationId or zone
    if lookup_zone:
        query = query.filter(Vehicle.zone == lookup_zone)
    vehicles = query.filter(Vehicle.status == VehicleStatus.AVAILABLE.value).order_by(Vehicle.id).all()
    return [serialize_vehicle(vehicle) for vehicle in vehicles]


@app.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = get_vehicle_or_404(db, vehicle_id)
    return serialize_vehicle(vehicle)


@app.patch("/vehicles/{vehicle_id}/status")
def patch_vehicle_status(vehicle_id: int, payload: VehicleStatusPayload, db: Session = Depends(get_db)):
    vehicle = get_vehicle_or_404(db, vehicle_id)
    vehicle.status = payload.status.value
    db.commit()
    return {"success": True, "status": vehicle.status}


@app.post("/vehicles/telemetry")
def create_telemetry(payload: TelemetryPayload, db: Session = Depends(get_db)):
    get_vehicle_or_404(db, payload.vehicleId)
    snapshot = TelemetrySnapshot(
        vehicle_id=payload.vehicleId,
        battery_level=payload.batteryLevel,
        tire_pressure_ok=str(payload.tirePressureOk).lower(),
        severity=payload.severity,
        fault_code=payload.faultCode,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    if telemetry_requires_attention(
        battery_level=payload.batteryLevel,
        tire_pressure_ok=payload.tirePressureOk,
        severity=payload.severity,
        fault_code=payload.faultCode,
    ):
        publish_event(
            "vehicle.telemetry_alert",
            {
                "telemetrySnapshotId": snapshot.id,
                "vehicleId": payload.vehicleId,
                "batteryLevel": payload.batteryLevel,
                "tirePressureOk": payload.tirePressureOk,
                "severity": payload.severity,
                "faultCode": payload.faultCode,
                "createdAt": iso(snapshot.created_at),
            },
        )
    return {"message": "Telemetry captured", "severity": snapshot.severity}


@app.get("/vehicles/{vehicle_id}/telemetry/latest")
def latest_telemetry(vehicle_id: int, db: Session = Depends(get_db)):
    get_vehicle_or_404(db, vehicle_id)
    snapshot = (
        db.query(TelemetrySnapshot)
        .filter(TelemetrySnapshot.vehicle_id == vehicle_id)
        .order_by(TelemetrySnapshot.created_at.desc(), TelemetrySnapshot.id.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Telemetry not found")
    return {
        "vehicleId": snapshot.vehicle_id,
        "batteryLevel": snapshot.battery_level,
        "tirePressureOk": snapshot.tire_pressure_ok == "true",
        "severity": snapshot.severity,
        "faultCode": snapshot.fault_code,
        "createdAt": iso(snapshot.created_at),
    }


class VehicleGrpcService(vehicle_pb2_grpc.VehicleServiceServicer):
    def CheckAvailability(self, request, context):
        """Operational eligibility check used before booking conflict checks.

        Despite the legacy RPC name, this does not answer whether the vehicle is
        free right now. Booking Service remains the source of truth for overlap
        checks on a requested booking window.
        """
        with SessionLocal() as db:
            vehicle = db.get(Vehicle, request.vehicle_id)
            if not vehicle:
                return vehicle_pb2.VehicleAvailabilityResponse(available=False, status="NOT_FOUND", message="Vehicle not found")
            available = is_operationally_eligible(vehicle)
            return vehicle_pb2.VehicleAvailabilityResponse(
                available=available,
                status=vehicle.status,
                message="Vehicle is operationally eligible" if available else "Vehicle is operationally blocked",
            )

    def UnlockVehicle(self, request, context):
        with SessionLocal() as db:
            vehicle = db.get(Vehicle, request.vehicle_id)
            if not vehicle:
                return vehicle_pb2.VehicleCommandResponse(success=False, status="NOT_FOUND", message="Unknown vehicle")
            if vehicle.status not in {VehicleStatus.AVAILABLE.value, VehicleStatus.BOOKED.value}:
                return vehicle_pb2.VehicleCommandResponse(success=False, status=vehicle.status, message="Vehicle cannot be unlocked")
            vehicle.status = VehicleStatus.IN_USE.value
            db.commit()
            return vehicle_pb2.VehicleCommandResponse(success=True, status=vehicle.status, message="Vehicle unlocked")


    def LockVehicle(self, request, context):
        with SessionLocal() as db:
            vehicle = db.get(Vehicle, request.vehicle_id)
            if not vehicle:
                return vehicle_pb2.VehicleCommandResponse(success=False, status="NOT_FOUND", message="Unknown vehicle")
            if vehicle.status not in LOCK_PRESERVED_STATUSES:
                vehicle.status = VehicleStatus.AVAILABLE.value
            db.commit()
            return vehicle_pb2.VehicleCommandResponse(success=True, status=vehicle.status, message="Vehicle locked")

    def UpdateVehicleStatus(self, request, context):
        with SessionLocal() as db:
            vehicle = db.get(Vehicle, request.vehicle_id)
            if not vehicle:
                return vehicle_pb2.VehicleStatusUpdateResponse(success=False, status="NOT_FOUND")
            vehicle.status = request.status
            db.commit()
            return vehicle_pb2.VehicleStatusUpdateResponse(success=True, status=vehicle.status)


def start_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    vehicle_pb2_grpc.add_VehicleServiceServicer_to_server(VehicleGrpcService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()

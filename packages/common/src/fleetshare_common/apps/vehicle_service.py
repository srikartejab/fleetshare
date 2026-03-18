from __future__ import annotations

import threading
from concurrent import futures
from datetime import datetime

import grpc
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.contracts import VehicleStatus
from fleetshare_common.database import Base, SessionLocal, engine, get_db
from fleetshare_common.generated import vehicle_pb2, vehicle_pb2_grpc

app = create_app("Vehicle Service", "Atomic vehicle state and telemetry service.")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True)
    model: Mapped[str] = mapped_column(String(128))
    zone: Mapped[str] = mapped_column(String(64))
    vehicle_type: Mapped[str] = mapped_column(String(64), default="SEDAN")
    status: Mapped[str] = mapped_column(String(64), default=VehicleStatus.AVAILABLE.value)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TelemetrySnapshot(Base):
    __tablename__ = "telemetry_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    battery_level: Mapped[int] = mapped_column(Integer, default=100)
    tire_pressure_ok: Mapped[str] = mapped_column(String(16), default="true")
    severity: Mapped[str] = mapped_column(String(32), default="INFO")
    fault_code: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VehicleStatusPayload(BaseModel):
    status: VehicleStatus


class TelemetryPayload(BaseModel):
    vehicleId: int
    batteryLevel: int = 100
    tirePressureOk: bool = True
    severity: str = "INFO"
    faultCode: str = ""


def seed_data():
    with SessionLocal() as db:
        if db.query(Vehicle).count():
            return
        vehicles = [
            Vehicle(id=1, plate_number="SFA1001A", model="Tesla Model 3", zone="SMU", vehicle_type="SEDAN"),
            Vehicle(id=2, plate_number="SFA1002B", model="BYD Atto 3", zone="SMU", vehicle_type="SUV"),
            Vehicle(id=3, plate_number="SFA1003C", model="Hyundai Kona", zone="TAMPINES", vehicle_type="SUV"),
            Vehicle(id=4, plate_number="SFA1004D", model="BMW i3", zone="SMU", vehicle_type="COMPACT"),
        ]
        db.add_all(vehicles)
        for vehicle in vehicles:
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
    Base.metadata.create_all(bind=engine)
    seed_data()
    threading.Thread(target=start_grpc_server, daemon=True).start()


@app.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    return [
        {
            "id": vehicle.id,
            "plateNumber": vehicle.plate_number,
            "model": vehicle.model,
            "zone": vehicle.zone,
            "vehicleType": vehicle.vehicle_type,
            "status": vehicle.status,
        }
        for vehicle in db.query(Vehicle).order_by(Vehicle.id).all()
    ]


@app.get("/vehicles/availability")
def get_vehicle_availability(zone: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Vehicle)
    if zone:
        query = query.filter(Vehicle.zone == zone)
    vehicles = query.filter(Vehicle.status == VehicleStatus.AVAILABLE.value).order_by(Vehicle.id).all()
    return [
        {
            "vehicleId": vehicle.id,
            "plateNumber": vehicle.plate_number,
            "model": vehicle.model,
            "zone": vehicle.zone,
            "vehicleType": vehicle.vehicle_type,
            "status": vehicle.status,
        }
        for vehicle in vehicles
    ]


@app.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = get_vehicle_or_404(db, vehicle_id)
    return {
        "id": vehicle.id,
        "plateNumber": vehicle.plate_number,
        "model": vehicle.model,
        "zone": vehicle.zone,
        "vehicleType": vehicle.vehicle_type,
        "status": vehicle.status,
    }


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
        "createdAt": snapshot.created_at.isoformat(),
    }


class VehicleGrpcService(vehicle_pb2_grpc.VehicleServiceServicer):
    def CheckAvailability(self, request, context):
        with SessionLocal() as db:
            vehicle = db.get(Vehicle, request.vehicle_id)
            if not vehicle:
                return vehicle_pb2.VehicleAvailabilityResponse(available=False, status="NOT_FOUND", message="Vehicle not found")
            available = vehicle.status == VehicleStatus.AVAILABLE.value
            return vehicle_pb2.VehicleAvailabilityResponse(
                available=available,
                status=vehicle.status,
                message="Vehicle can be reserved" if available else "Vehicle is unavailable",
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
            if vehicle.status != VehicleStatus.MAINTENANCE_REQUIRED.value:
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

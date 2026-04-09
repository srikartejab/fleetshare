from __future__ import annotations

import grpc

from fleetshare_common.generated import vehicle_pb2, vehicle_pb2_grpc
from fleetshare_common.settings import get_settings


def stub():
    settings = get_settings()
    channel = grpc.insecure_channel(settings.vehicle_grpc_target)
    return vehicle_pb2_grpc.VehicleServiceStub(channel)


def check_operational_eligibility(vehicle_id: int):
    response = stub().CheckAvailability(vehicle_pb2.VehicleAvailabilityRequest(vehicle_id=vehicle_id))
    return {"available": response.available, "status": response.status, "message": response.message}


def check_availability(vehicle_id: int):
    """Backward-compatible alias for the operational-eligibility RPC."""

    return check_operational_eligibility(vehicle_id)


def unlock_vehicle(vehicle_id: int, booking_id: str, user_id: str):
    response = stub().UnlockVehicle(
        vehicle_pb2.VehicleCommandRequest(vehicle_id=vehicle_id, booking_id=booking_id, user_id=user_id)
    )
    return {"success": response.success, "status": response.status, "message": response.message}


def lock_vehicle(vehicle_id: int, booking_id: str, user_id: str):
    response = stub().LockVehicle(
        vehicle_pb2.VehicleCommandRequest(vehicle_id=vehicle_id, booking_id=booking_id, user_id=user_id)
    )
    return {"success": response.success, "status": response.status, "message": response.message}


def update_vehicle_status(vehicle_id: int, status: str):
    response = stub().UpdateVehicleStatus(
        vehicle_pb2.VehicleStatusUpdateRequest(vehicle_id=vehicle_id, status=status)
    )
    return {"success": response.success, "status": response.status}


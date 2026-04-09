import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from types import SimpleNamespace

from fleetshare_common.apps import vehicle_service


class _FakeSession:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _model, vehicle_id):
        return self.vehicle if self.vehicle and self.vehicle.id == vehicle_id else None

    def commit(self):
        self.committed = True


def test_check_availability_treats_in_use_vehicle_as_operationally_eligible(monkeypatch):
    service = vehicle_service.VehicleGrpcService()
    vehicle = SimpleNamespace(id=7, status="IN_USE")
    monkeypatch.setattr(vehicle_service, "SessionLocal", lambda: _FakeSession(vehicle))

    response = service.CheckAvailability(SimpleNamespace(vehicle_id=7), None)

    assert response.available is True
    assert response.status == "IN_USE"


def test_check_availability_rejects_maintenance_vehicle(monkeypatch):
    service = vehicle_service.VehicleGrpcService()
    vehicle = SimpleNamespace(id=8, status="MAINTENANCE_REQUIRED")
    monkeypatch.setattr(vehicle_service, "SessionLocal", lambda: _FakeSession(vehicle))

    response = service.CheckAvailability(SimpleNamespace(vehicle_id=8), None)

    assert response.available is False
    assert response.status == "MAINTENANCE_REQUIRED"


def test_lock_vehicle_preserves_under_inspection_state(monkeypatch):
    service = vehicle_service.VehicleGrpcService()
    vehicle = SimpleNamespace(id=9, status="UNDER_INSPECTION")
    session = _FakeSession(vehicle)
    monkeypatch.setattr(vehicle_service, "SessionLocal", lambda: session)

    response = service.LockVehicle(SimpleNamespace(vehicle_id=9), None)

    assert response.success is True
    assert response.status == "UNDER_INSPECTION"
    assert vehicle.status == "UNDER_INSPECTION"
    assert session.committed is True

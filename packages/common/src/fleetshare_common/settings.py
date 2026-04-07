from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    service_name: str = "fleetshare"
    service_port: int = 8000
    database_url: str = ""
    db_startup_timeout_seconds: int = 60
    db_startup_retry_interval_seconds: int = 2
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    rabbitmq_exchange: str = "fleetshare.events"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "fleetshare-evidence"
    minio_secure: bool = False
    kong_public_url: str = "http://localhost:8000"
    web_api_base_url: str = "http://localhost:8000"
    billing_timezone: str = "Asia/Singapore"
    damage_booking_lookahead_hours: int = 336
    azure_vision_mode: str = "mock"
    azure_vision_endpoint: str = ""
    azure_vision_key: str = ""
    vehicle_service_url: str = "http://vehicle-service:8000"
    vehicle_grpc_target: str = "vehicle-service:50051"
    booking_service_url: str = "http://booking-service:8000"
    trip_service_url: str = "http://trip-service:8000"
    record_service_url: str = "http://record-service:8000"
    maintenance_service_url: str = "http://maintenance-service:8000"
    maintenance_backend_mode: str = "outsystems"
    outsystems_maintenance_base_url: str = "https://personal-1p5qci9q.outsystemscloud.com/MaintenanceService/rest/maintenance"
    outsystems_maintenance_timeout_seconds: int = 20
    pricing_service_url: str = "http://pricing-service:8000"
    payment_service_url: str = "http://payment-service:8000"
    notification_service_url: str = "http://notification-service:8000"
    search_service_url: str = "http://search-available-vehicles-service:8000"
    process_booking_service_url: str = "http://process-booking-service:8000"
    external_damage_service_url: str = "http://external-damage-service:8000"
    start_trip_service_url: str = "http://start-trip-service:8000"
    internal_damage_service_url: str = "http://internal-damage-service:8000"
    end_trip_service_url: str = "http://end-trip-service:8000"
    handle_damage_service_url: str = "http://handle-damage-service:8000"
    renewal_reconciliation_service_url: str = "http://renewal-reconciliation-service:8000"
    rental_execution_service_url: str = "http://rental-execution-service:8000"
    ops_console_service_url: str = "http://ops-console-service:8000"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    service_name = os.getenv("SERVICE_NAME", "fleetshare")
    service_port = int(os.getenv("SERVICE_PORT", "8000"))
    return Settings(service_name=service_name, service_port=service_port)

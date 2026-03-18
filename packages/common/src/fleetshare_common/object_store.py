from __future__ import annotations

import io
from typing import BinaryIO

import boto3
from botocore.client import Config

from fleetshare_common.settings import get_settings


def get_s3_client():
    settings = get_settings()
    endpoint = settings.minio_endpoint
    if not endpoint.startswith("http"):
        endpoint = f"http://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    settings = get_settings()
    client = get_s3_client()
    buckets = [bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])]
    if settings.minio_bucket not in buckets:
        client.create_bucket(Bucket=settings.minio_bucket)


def upload_bytes(key: str, raw: bytes, content_type: str = "application/octet-stream") -> str:
    settings = get_settings()
    ensure_bucket()
    client = get_s3_client()
    client.put_object(Bucket=settings.minio_bucket, Key=key, Body=io.BytesIO(raw), ContentType=content_type)
    return key

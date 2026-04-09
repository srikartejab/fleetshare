from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import pika

from fleetshare_common.contracts import EventEnvelope
from fleetshare_common.settings import get_settings

logger = logging.getLogger("fleetshare.messaging")
CONSUMER_RETRY_DELAY_SECONDS = 2


def _connection():
    settings = get_settings()
    return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))


def stable_event_id(*parts: Any) -> str:
    normalized = "|".join("" if part is None else str(part) for part in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, normalized))


def publish_event(event_type: str, payload: dict[str, Any], *, event_id: str | None = None):
    settings = get_settings()
    event = EventEnvelope(event_id=event_id or str(uuid.uuid4()), event_type=event_type, payload=payload)
    connection = _connection()
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=settings.rabbitmq_exchange, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=settings.rabbitmq_exchange,
            routing_key=event_type,
            body=event.model_dump_json(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.info(
            "published event",
            extra={"service": settings.service_name, "event_type": event_type, "event_id": event.event_id},
        )
    finally:
        connection.close()


def start_consumer(queue_name: str, routing_keys: list[str], callback: Callable[[dict[str, Any]], None]):
    settings = get_settings()

    def runner():
        while True:
            connection = None
            try:
                connection = _connection()
                channel = connection.channel()
                channel.exchange_declare(exchange=settings.rabbitmq_exchange, exchange_type="topic", durable=True)
                channel.queue_declare(queue=queue_name, durable=True)
                for routing_key in routing_keys:
                    channel.queue_bind(exchange=settings.rabbitmq_exchange, queue=queue_name, routing_key=routing_key)
                logger.info(
                    "consumer ready",
                    extra={"service": settings.service_name, "queue": queue_name, "routing_keys": ",".join(routing_keys)},
                )

                def on_message(_channel, _method, _properties, body: bytes):
                    payload = json.loads(body.decode("utf-8"))
                    try:
                        callback(payload)
                    except Exception:
                        logger.exception(
                            "consumer callback failed",
                            extra={
                                "service": settings.service_name,
                                "queue": queue_name,
                                "event_id": payload.get("event_id"),
                                "event_type": payload.get("event_type"),
                            },
                        )
                        _channel.basic_nack(delivery_tag=_method.delivery_tag, requeue=True)
                        return
                    logger.info(
                        "consumed event",
                        extra={
                            "service": settings.service_name,
                            "queue": queue_name,
                            "event_id": payload.get("event_id"),
                            "event_type": payload.get("event_type"),
                        },
                    )
                    _channel.basic_ack(delivery_tag=_method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=queue_name, on_message_callback=on_message)
                channel.start_consuming()
                logger.warning(
                    "consumer stopped unexpectedly; retrying",
                    extra={"service": settings.service_name, "queue": queue_name},
                )
            except Exception:
                logger.exception(
                    "consumer connection failed; retrying",
                    extra={"service": settings.service_name, "queue": queue_name},
                )
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        logger.debug("consumer connection close failed", exc_info=True)
            time.sleep(CONSUMER_RETRY_DELAY_SECONDS)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


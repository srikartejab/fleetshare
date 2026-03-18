from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from typing import Any

import pika

from fleetshare_common.contracts import EventEnvelope
from fleetshare_common.settings import get_settings


def _connection():
    settings = get_settings()
    return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))


def publish_event(event_type: str, payload: dict[str, Any]):
    settings = get_settings()
    event = EventEnvelope(event_id=str(uuid.uuid4()), event_type=event_type, payload=payload)
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
    finally:
        connection.close()


def start_consumer(queue_name: str, routing_keys: list[str], callback: Callable[[dict[str, Any]], None]):
    settings = get_settings()

    def runner():
        connection = _connection()
        channel = connection.channel()
        channel.exchange_declare(exchange=settings.rabbitmq_exchange, exchange_type="topic", durable=True)
        channel.queue_declare(queue=queue_name, durable=True)
        for routing_key in routing_keys:
            channel.queue_bind(exchange=settings.rabbitmq_exchange, queue=queue_name, routing_key=routing_key)

        def on_message(_channel, _method, _properties, body: bytes):
            payload = json.loads(body.decode("utf-8"))
            callback(payload)
            _channel.basic_ack(delivery_tag=_method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=queue_name, on_message_callback=on_message)
        channel.start_consuming()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


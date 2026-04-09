import pytest

from fleetshare_common import messaging


class _FakeChannel:
    def exchange_declare(self, **_kwargs):
        return None

    def queue_declare(self, **_kwargs):
        return None

    def queue_bind(self, **_kwargs):
        return None

    def basic_qos(self, **_kwargs):
        return None

    def basic_consume(self, **_kwargs):
        return None

    def start_consuming(self):
        raise SystemExit


class _FakeConnection:
    def __init__(self):
        self.closed = False
        self.channel_instance = _FakeChannel()

    def channel(self):
        return self.channel_instance

    def close(self):
        self.closed = True


class _ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


def test_start_consumer_retries_until_connection_succeeds(monkeypatch):
    attempts = {"count": 0}
    sleeps = []
    connections = []

    def fake_connection():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("rabbit unavailable")
        connection = _FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(
        messaging,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "rabbitmq_url": "amqp://guest:guest@rabbitmq:5672/",
                "rabbitmq_exchange": "fleetshare.events",
                "service_name": "test-service",
            },
        )(),
    )
    monkeypatch.setattr(messaging, "_connection", fake_connection)
    monkeypatch.setattr(messaging.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(messaging.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(SystemExit):
        messaging.start_consumer("test-queue", ["event.key"], lambda payload: None)

    assert attempts["count"] == 2
    assert sleeps == [messaging.CONSUMER_RETRY_DELAY_SECONDS]
    assert len(connections) == 1
    assert connections[0].closed is True

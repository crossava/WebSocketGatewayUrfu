import uuid

BROKERS = "212.113.117.163:9092,212.113.117.163:9094"

PRIMARY_CONFIG = {
    "bootstrap.servers": BROKERS,
}

CONSUMER_CONFIG = {
    "bootstrap.servers": BROKERS,
    "group.id": "websocketGateway_" + str(uuid.uuid4()),
    "auto.offset.reset": "latest",
    "enable.auto.commit": True,
    "session.timeout.ms": 10000,
}

PRODUCER_CONFIG = {
    "bootstrap.servers": BROKERS,  # Список брокеров
}

STATUS_RESPONSE_TOPIC = "online_status_responses"

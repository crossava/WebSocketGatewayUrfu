import uuid

BROKERS = "77.232.135.48:9092,77.232.135.48:9094"

PRIMARY_CONFIG = {
    "bootstrap.servers": BROKERS,
}

CONSUMER_CONFIG = {
    "bootstrap.servers": BROKERS,
    "group.id": "websocketGateway_" + str(uuid.uuid4()),
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
    "session.timeout.ms": 10000,
}

PRODUCER_CONFIG = {
    "bootstrap.servers": BROKERS,  # Список брокеров
}

STATUS_RESPONSE_TOPIC = "online_status_responses"

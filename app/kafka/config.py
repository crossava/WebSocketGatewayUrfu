BROKERS = "94.241.138.149:9092,94.241.138.149:9094"

PRIMARY_CONFIG = {
    "bootstrap.servers": BROKERS,
}

CONSUMER_CONFIG = {
    "bootstrap.servers": BROKERS,
    "group.id": "websocketGateway_prod",
    "auto.offset.reset": "earliest",  # Начало чтения с первого сообщения
    "enable.auto.commit": True,  # Автофиксирование offset'ов
    "session.timeout.ms": 10000,  # Таймаут сессии увеличен
}

PRODUCER_CONFIG = {
    "bootstrap.servers": BROKERS,  # Список брокеров
}

STATUS_RESPONSE_TOPIC = "online_status_responses"

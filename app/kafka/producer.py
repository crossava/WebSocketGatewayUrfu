import json
from confluent_kafka import Producer
import logging

logger = logging.getLogger("kafka")
logger.setLevel(logging.ERROR)


def produce_message(config, topic, message):
    """Отправка сообщений в Kafka."""
    try:
        producer = Producer(config)

        if isinstance(message, dict):
            message = json.dumps(message)

        producer.produce(topic, value=message.encode('utf-8'))
        producer.flush()  # 🔥 Дожидаемся отправки в Kafka

    except Exception as e:
        logger.error(f"Ошибка Kafka: {e}")
        raise Exception(f"Ошибка отправки сообщения: {e}")

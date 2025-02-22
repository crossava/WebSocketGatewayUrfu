import asyncio
import json
from confluent_kafka import Consumer, KafkaError
import logging
from fastapi.responses import JSONResponse
from fastapi import Cookie, Response

from app.gateway.websocket_gateway import ws_manager
from app.gateway.websocket_manager import WebSocketManager

logger = logging.getLogger("kafka")
logger.setLevel(logging.ERROR)


async def handle_response(message, request_manager):
    """Обработка сообщений из Kafka."""
    try:
        raw_message = message.value()

        # Проверяем, что сообщение не None и не пустая строка
        if not raw_message:
            logger.error("Получено пустое сообщение из Kafka")
            return

        raw_message = raw_message.decode("utf-8").strip()

        if not raw_message:
            logger.error("Сообщение после декодирования пустое")
            return

        # Преобразуем в JSON
        response = json.loads(raw_message)

        request_id = response.get("request_id")
        if not request_id:
            logger.error("Ошибка: request_id отсутствует в сообщении")
            return

        to_user_id = response.get("to_user_id")
        if to_user_id:
            await ws_manager.send_message(to_user_id, response)  # ✅ Отправляем WebSocket

        print("response", response)
        event = await request_manager.get_request(request_id)
        if isinstance(event, asyncio.Event):
            await request_manager.add_request(request_id, response)  # Сохраняем ответ
            event.set()  # Разблокируем login()
        else:
            websocket = event
            if websocket:
                await websocket.send_json(response)
                await request_manager.remove_request(request_id)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка JSON-декодирования: {e}, raw_message={raw_message}")
    except Exception as e:
        logger.error(f"Ошибка обработки Kafka сообщения: {e}")


def consume_responses(config, topics, request_manager):
    """Чтение ответов из Kafka."""
    consumer = Consumer(config)
    consumer.subscribe(topics)

    print(f"Подписка на топики: {topics}")

    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Ошибка консюмера: {msg.error()}")
                continue

        try:
            asyncio.run(handle_response(msg, request_manager))
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")

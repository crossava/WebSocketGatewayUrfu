import asyncio
import json
from confluent_kafka import Consumer, KafkaError
import logging

from starlette.websockets import WebSocket

from app.gateway.websocket_gateway import ws_manager
from app.gateway.request_manager import RequestManager

logger = logging.getLogger("kafka")
logger.setLevel(logging.ERROR)


async def handle_response(message, request_manager: RequestManager):
    """Обработка сообщений из Kafka."""
    try:
        raw_message = message.value().decode("utf-8")
        response = json.loads(raw_message)

        if response.get("only_forward"):
            forward_to = response.get("forward_to")
            if forward_to:
                if isinstance(forward_to, str):
                    await ws_manager.send_message(forward_to, response)
                elif isinstance(forward_to, list):
                    for target_user_id in forward_to:
                        await ws_manager.send_message(target_user_id, response)
            return

        request_id = response.get("request_id")
        if not request_id:
            return

        request_obj = await request_manager.get_request(request_id)
        if not request_obj:
            return

        if isinstance(request_obj, WebSocket):
            user_id = None
            for (uid), ws in ws_manager.active_connections.items():
                if ws == request_obj:
                    user_id = uid
                    break

            if not user_id:
                return

            await ws_manager.send_message(user_id, response)

            forward_to = response.get("forward_to")
            if forward_to:
                if isinstance(forward_to, str):
                    await ws_manager.send_message(forward_to, response)
                elif isinstance(forward_to, list):
                    for target_user_id in forward_to:
                        await ws_manager.send_message(target_user_id, response)

            await request_manager.remove_request(request_id)

        elif isinstance(request_obj, asyncio.Event):
            await request_manager.add_request(request_id, response)  # Сохраняем ответ
            request_obj.set()

    except Exception as e:
        logger.error(f"Ошибка обработки Kafka сообщения: {e}")
        print(f"Ошибка обработки Kafka сообщения: {e}")


def consume_responses(config, topics, request_manager: RequestManager):
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
                print(f"❌ Ошибка консюмера: {msg.error()}")
                continue

        try:
            print("📩 msg: ", msg)
            asyncio.run(handle_response(msg, request_manager))
        except Exception as e:
            print(f"❌ Ошибка обработки сообщения: {e}")

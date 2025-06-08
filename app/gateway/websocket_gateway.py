import os
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

from app.gateway.request_manager import RequestManager
from app.gateway.websocket_manager import WebSocketManager
from app.kafka.producer import produce_message
from app.kafka.config import PRIMARY_CONFIG
import uuid
import logging

import json

logger = logging.getLogger("kafka")
logger.setLevel(logging.ERROR)

request_manager = RequestManager()
ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    headers = dict(websocket.headers)
    cookies = headers.get("cookie", "")
    cookies_dict = {cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies.split("; ") if "=" in cookie}
    access_token = cookies_dict.get("access_token")
    user_id = cookies_dict.get("user_id")

    print("access_token", access_token)

    if not access_token or not user_id:
        print(f"{now()} - Ошибка: соединение WebSocket отклонено. Отсутствует access_token или user_id.")
        await websocket.close(code=1008)
        return

    print(f"{now()} - Пользователь {user_id} успешно подключился. access_token:")
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            print(f"{now()} - Получено сообщение от пользователя {user_id}: {data}")

            print("data", data)
            topic_name = data.get("topic")
            message = data.get("message")

            if not message or not isinstance(message, dict):
                print(f"{now()} - Ошибка формата сообщения от пользователя {user_id}: {data}")
                await websocket.send_text(json.dumps(
                    {"request_id": str(uuid.uuid4()), "status": "error", "message": "Неверный формат сообщения"}))
                continue

            request_id = data.get("request_id", str(uuid.uuid4()))
            kafka_message = {
                "request_id": request_id,
                "message": message
            }

            try:
                await request_manager.add_request(request_id, websocket)
                print(f"{now()} - Зарегистрирован request_id {request_id} для пользователя {user_id}")
                produce_message(PRIMARY_CONFIG, topic_name, kafka_message)
            except Exception as kafka_error:
                logger.error(f"{now()} - Ошибка отправки сообщения в Kafka для пользователя {user_id}: {kafka_error}")
                await websocket.send_text(json.dumps({"error": f"Ошибка отправки в Kafka: {str(kafka_error)}"}))

    except WebSocketDisconnect as e:
        code = getattr(e, "code", "нет кода")
        reason = getattr(e, "reason", "нет причины")
        print(f"{now()} - Пользователь {user_id} отключился от WebSocket. Код: {code}. Причина: {reason}")
        await ws_manager.disconnect(user_id)

    except Exception as e:
        logger.error(f"{now()} - Общая ошибка WebSocket для пользователя {user_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception as send_error:
            print(f"{now()} - Ошибка при отправке сообщения об ошибке пользователю {user_id}: {send_error}")
        logger.error(f"{now()} - Общая ошибка WebSocket для пользователя {user_id}: {e}")

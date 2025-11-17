import os
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.gateway.request_manager import RequestManager
from app.gateway.websocket_manager import WebSocketManager
from app.kafka.producer import produce_message
from app.kafka.config import PRIMARY_CONFIG
import uuid
import logging

import json

from app.registry import online_status_manager

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

    # Подключение разрешено даже без access_token и user_id
    print(f"{now()} - Пользователь {'анонимный' if not user_id else user_id} подключился к WebSocket.")
    await ws_manager.connect(websocket, user_id or "anonymous")

    try:
        while True:
            data = await websocket.receive_json()
            print(f"{now()} - Получено сообщение от пользователя {'анонимный' if not user_id else user_id}: {data}")

            topic_name = data.get("topic")
            action = data.get("action")
            payload = data.get("payload")

            # if not message or not isinstance(message, dict):
            #     print(f"{now()} - Ошибка формата сообщения: {data}")
            #     await websocket.send_text(json.dumps(
            #         {"request_id": str(uuid.uuid4()), "status": "error", "message": "Неверный формат сообщения"}
            #     ))
            #     continue

            # Проверка действия

            # Разрешено только get_upcoming_events для неавторизованных пользователей
            if not user_id or not access_token:
                if action != "get_upcoming_events":
                    print(f"{now()} - Ошибка: действие '{action}' требует авторизации (user_id и access_token).")
                    await websocket.send_text(json.dumps(
                        {"request_id": str(uuid.uuid4()), "status": "error", "message": "Требуется авторизация"}
                    ))
                    continue

            request_id = data.get("request_id", str(uuid.uuid4()))
            kafka_message = {
                "request_id": request_id,
                "action": action,
                "payload": payload
            }

            try:
                await request_manager.add_request(request_id, websocket)
                print(f"{now()} - Зарегистрирован request_id {request_id} для пользователя {'анонимный' if not user_id else user_id}")
                produce_message(PRIMARY_CONFIG, topic_name, kafka_message)
            except Exception as kafka_error:
                logger.error(f"{now()} - Ошибка отправки сообщения в Kafka: {kafka_error}")
                await websocket.send_text(json.dumps({"error": f"Ошибка отправки в Kafka: {str(kafka_error)}"}))

    except WebSocketDisconnect as e:
        code = getattr(e, "code", "нет кода")
        reason = getattr(e, "reason", "нет причины")
        print(f"{now()} - Пользователь {'анонимный' if not user_id else user_id} отключился от WebSocket. Код: {code}. Причина: {reason}")
        await ws_manager.disconnect(user_id or "anonymous")

    except Exception as e:
        logger.error(f"{now()} - Общая ошибка WebSocket для пользователя {'анонимный' if not user_id else user_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception as send_error:
            print(f"{now()} - Ошибка при отправке сообщения об ошибке: {send_error}")
        logger.error(f"{now()} - Общая ошибка WebSocket: {e}")
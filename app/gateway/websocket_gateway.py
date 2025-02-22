import os
from datetime import datetime

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Depends, Cookie, Response
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.gateway.middleware import WebSocketTokenMiddleware
from app.gateway.request_manager import RequestManager  # Импорт менеджера запросов
from app.gateway.websocket_manager import WebSocketManager
from app.kafka.producer import produce_message
from app.kafka.config import PRIMARY_CONFIG
import uuid
import asyncio
import logging
from fastapi import Request
from fastapi import HTTPException
import httpx

from typing import Optional
import json
import socket

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,  # 🔥 ОБЯЗАТЕЛЬНО для работы с куками
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(WebSocketTokenMiddleware)

logger = logging.getLogger("kafka")
logger.setLevel(logging.ERROR)

# Создаём единственный экземпляр RequestManager
request_manager = RequestManager()
ws_manager = WebSocketManager()


class LoginRequest(BaseModel):
    username: str
    password: str
    device_type: Optional[str] = 'unknown'
    device_name: Optional[str] = 'unknown'


@app.post("/login")
async def login(request: LoginRequest):
    """Эндпоинт для авторизации пользователя."""
    print("запрос пришел")
    request_id = str(uuid.uuid4())
    kafka_message = {
        "request_id": request_id,
        "message": {
            "action": "auth_user",
            "username": request.username,
            "password": request.password,
            "device_type": request.device_type,
            "device_name": request.device_name
        }
    }

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)
        produce_message(PRIMARY_CONFIG, "user_requests", kafka_message)

        await asyncio.wait_for(event.wait(), timeout=10.0)

        response_data = await request_manager.get_request(request_id)

        print(f"📩 response_data: {response_data}")

        if response_data:
            response_body = response_data.get("message", {}).get("body", {})

            if not response_body:
                print(f"❌ response_body пустой, response_data: {response_data}")
                raise HTTPException(status_code=500, detail="Ошибка в ответе Kafka")

            access_token = response_body.pop("access_token")
            refresh_token = response_body.pop("refresh_token")
            user_id = response_body.get("user_id")

            if access_token and refresh_token:
                response = JSONResponse(content=response_data)
                response.set_cookie(

                    key="access_token",
                    value=str(access_token),
                    httponly=True,
                    samesite='None',
                    secure=False
                )
                response.set_cookie(
                    key="refresh_token",
                    value=str(refresh_token),
                    httponly=True,
                    samesite='None',
                    secure=False
                )
                response.set_cookie(
                    key="user_id",
                    value=str(user_id),
                    httponly=True,
                    samesite='None',
                    secure=False
                )
                response.status_code = 200
                return response
            else:
                raise HTTPException(status_code=500, detail="Токены отсутствуют в ответе")
        else:
            raise HTTPException(status_code=500, detail="Ошибка авторизации")
    except asyncio.TimeoutError:
        print(f"❌ Время ожидания истекло для request_id={request_id}")
        await request_manager.remove_request(request_id)
        raise HTTPException(status_code=504, detail="Время ожидания ответа истекло")
    except Exception as e:
        logger.error(f"⚠️ Ошибка при обработке запроса: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")


@app.post("/refresh-token")
async def refresh_token(request: Request):
    """Эндпоинт для обновления токена пользователя."""
    print("запрос на обновление токена пришел")
    request_id = str(uuid.uuid4())

    # Получаем refresh_token из куков
    refresh_token = request.cookies.get("refresh_token")
    user_id = request.cookies.get("user_id")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token отсутствует")

    print("send refresh for refresh token: ", refresh_token)
    kafka_message = {
        "request_id": request_id,
        "message": {
            "action": "refresh_token",
            "refresh_token": refresh_token
        }
    }

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)  # Добавляем request_id с asyncio.Event
        produce_message(PRIMARY_CONFIG, "auth_requests", kafka_message)

        # Ожидаем ответ от Kafka (максимум 10 секунд)
        await asyncio.wait_for(event.wait(), timeout=10.0)

        # Получаем сохранённый ответ
        response_data = await request_manager.get_request(request_id)
        if response_data:
            print("response data get for refresh token: ", response_data)
            response_body = response_data.get("message", {}).get("body", {})
            access_token = response_body.pop("access_token", None)  # Удаляем и получаем access_token
            refresh_token = response_body.pop("refresh_token", None)  # Удаляем и получаем refresh_token

            if access_token and refresh_token:
                response = JSONResponse(content=response_data)
                response.set_cookie(
                    key="access_token",
                    value=str(access_token),
                    httponly=True,
                    samesite='None',
                    secure=False
                )
                response.set_cookie(
                    key="refresh_token",
                    value=str(refresh_token),
                    httponly=True,
                    samesite='None',
                    secure=False
                )

                response.set_cookie(
                    key="user_id",
                    value=str(user_id),
                    httponly=True,
                    samesite='None',
                    secure=False
                )


                response.status_code = 200
                return response
            else:
                raise HTTPException(status_code=500, detail="Токены отсутствуют в ответе")
        else:
            raise HTTPException(status_code=500, detail="Ошибка обновления токена")
    except asyncio.TimeoutError:
        await request_manager.remove_request(request_id)
        raise HTTPException(status_code=504, detail="Время ожидания ответа истекло")
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса в Kafka: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")


# @app.get("/logout")
# async def logout(request: Request, response: Response):
#     """Эндпоинт для выхода пользователя, удаляющий куки и отправляющий событие в Kafka."""
#
#     request_id = str(uuid.uuid4())
#
#     # Получаем refresh_token из куков
#     refresh_token = request.cookies.get("refresh_token")
#
#     if not refresh_token:
#         logger.warning("Попытка выхода без refresh_token")
#         return {"status": "success", "message": "Вы вышли из системы, но refresh_token не был найден"}
#
#     # Удаляем куки
#     response.delete_cookie("access_token")
#     response.delete_cookie("refresh_token")
#     response.delete_cookie("user_id")
#
#     # Формируем сообщение для Kafka
#     disconnect_message = {
#         "request_id": request_id,
#         "message": {
#             "action": "revoke_refresh_tokensdf",
#             "refresh_token": refresh_token
#         }
#     }
#
#     try:
#         produce_message(PRIMARY_CONFIG, 'auth_requests', disconnect_message)
#         print(f"📤 Отправлено сообщение о разрыве соединения")
#     except Exception as kafka_error:
#         logger.error(f"Ошибка при отправке сообщения о разрыве в Kafka: {kafka_error}")
#
#     return response


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    middle_name: str
    email: str
    birth_date: str
    password: str
    check_password: str
    verification_code: str


@app.post("/register")
async def register(request: RegisterRequest):
    """Эндпоинт для регистрации пользователя."""
    print("Запрос на регистрацию получен")
    request_id = str(uuid.uuid4())

    kafka_message = {
        "request_id": request_id,
        "message": {
            "action": "register",
            "body": request.model_dump()
        }
    }

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)
        produce_message(PRIMARY_CONFIG, "user_requests", kafka_message)

        await asyncio.wait_for(event.wait(), timeout=10.0)

        response_data = await request_manager.get_request(request_id)
        if response_data:
            return JSONResponse(content=response_data)

        raise HTTPException(status_code=500, detail="Ошибка регистрации")
    except asyncio.TimeoutError:
        await request_manager.remove_request(request_id)
        raise HTTPException(status_code=504, detail="Время ожидания ответа истекло")
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса в Kafka: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    # headers = dict(websocket.headers)
    # cookies = headers.get("cookie", "")
    # cookies_dict = {cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies.split("; ") if "=" in cookie}
    # access_token = cookies_dict.get("access_token")
    # user_id = cookies_dict.get("user_id")
    # client_host = websocket.client.host
    # client_port = websocket.client.port
    #
    # if not access_token or not user_id:
    #     print(f"{now()} - Ошибка: соединение WebSocket отклонено. Отсутствует access_token или user_id.")
    #     await websocket.close(code=1008)
    #     return

    user_id = "123321"

    print(f"{now()} - Пользователь {user_id} успешно подключился. access_token:")
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            print(f"{now()} - Получено сообщение от пользователя {user_id}: {data}")

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

import io
import logging
import uuid

from fastapi import Request, APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
from app.gateway.websocket_gateway import request_manager

import asyncio

from app.kafka.config import PRIMARY_CONFIG
from app.kafka.producer import produce_message

import boto3
from botocore.client import Config
from werkzeug.utils import secure_filename
from fastapi import APIRouter, Request, Form, File, UploadFile
from typing import List

router = APIRouter()
logger = logging.getLogger("api_routes")


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(request: LoginRequest):
    """Эндпоинт для авторизации пользователя."""
    print("запрос пришел")
    request_id = str(uuid.uuid4())
    kafka_message = {
        "request_id": request_id,
        "action": "login",
        "payload": {
            "email": request.email,
            "password": request.password
        }
    }

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)
        produce_message(PRIMARY_CONFIG, "identity_requests", kafka_message)

        await asyncio.wait_for(event.wait(), timeout=30)

        response_data = await request_manager.get_request(request_id)

        print(f"📩 response_data: {response_data}")

        if response_data:
            response_body = response_data.get("body", {})

            if not response_body:
                print(f"❌ response_body пустой, response_data: {response_data}")
                raise HTTPException(status_code=500, detail="Ошибка в ответе Kafka")

            access_token = response_body.pop("token")
            user_id = response_body.get("user").get("_id")

            if access_token:
                response = JSONResponse(content=response_data)
                response.set_cookie(
                    key="access_token",
                    value=str(access_token),
                    httponly=True,
                    samesite='None',
                    secure=True
                )
                response.set_cookie(
                    key="refresh_token",
                    value=str(refresh_token),
                    httponly=True,
                    samesite='None',
                    secure=True
                )
                response.set_cookie(
                    key="user_id",
                    value=str(user_id),
                    httponly=True,
                    samesite='None',
                    secure=True
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


@router.post("/refresh-token")
async def refresh_token(request: Request):
    """Эндпоинт для обновления токена пользователя."""
    print("запрос на обновление токена пришел")
    request_id = str(uuid.uuid4())

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
                    samesite=None,
                    secure=False
                )
                # response.set_cookie(
                #     key="refresh_token",
                #     value=str(refresh_token),
                #     httponly=True,
                #     samesite='None',
                #     secure=False
                # )

                # response.set_cookie(
                #     key="user_id",
                #     value=str(user_id),
                #     httponly=True,
                #     samesite='None',
                #     secure=False
                # )

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


class RegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str


@router.post("/register")
async def register(request: RegisterRequest):
    """Эндпоинт для регистрации пользователя."""
    print("Запрос на регистрацию получен")
    request_id = str(uuid.uuid4())

    kafka_message = {
        "request_id": request_id,
        "action": "create_user",
        "payload": {
            "email": request.email,
            "full_name": request.full_name,
            "password": "123123123",
            "role": "barista",
            "coffee_shop_id": "cs1",
            "phone": "+79998887766"
        }
    }
    print("Запрос на регистрацию отправлен в Kafka", kafka_message)

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)
        produce_message(PRIMARY_CONFIG, "identity_requests", kafka_message)

        await asyncio.wait_for(event.wait(), timeout=15)

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


class ConfirmRegisterRequest(BaseModel):
    email: str
    confirmation_code: str


@router.post("/confirm-registration")
async def register(request: ConfirmRegisterRequest):
    """Эндпоинт для регистрации пользователя."""
    print("Запрос на confirm получен")
    request_id = str(uuid.uuid4())

    kafka_message = {
        "request_id": request_id,
        "message": {
            "action": "confirm_email",
            "data": request.model_dump()
        }
    }
    print("Запрос на регистрацию отправлен в Kafka", kafka_message)

    try:
        event = asyncio.Event()
        await request_manager.add_request(request_id, event)
        produce_message(PRIMARY_CONFIG, "user_requests", kafka_message)

        await asyncio.wait_for(event.wait(), timeout=30.0)

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


s3 = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id="YCAJEuNsk5G5pzlsGcS19fuGR",
    aws_secret_access_key="YCOtUnaE1vgjH_shSozR8fkL71JSoRognKGKHgST",
    config=Config(signature_version="s3v4"),
    region_name="ru-central1"
)

BUCKET_NAME = "urfuupload"


def upload_file_to_yandex_s3(file_data: bytes, bucket: str, filename: str) -> str:
    s3.upload_fileobj(
        io.BytesIO(file_data),
        bucket,
        filename,
        ExtraArgs={"ACL": "public-read"}  # ВОТ ЭТА СТРОКА ВАЖНА
    )
    return f"https://{bucket}.storage.yandexcloud.net/{filename}"


@router.post("/upload-task-attachments")
async def upload_task_attachments(
        task_id: str = Form(...),  # можно убрать, если не нужен
        attachments: List[UploadFile] = File(...)
):
    uploaded = []
    for file in attachments:
        contents = await file.read()
        url = upload_file_to_yandex_s3(contents, BUCKET_NAME, file.filename)
        uploaded.append(url)

    return {"status": "success", "uploaded": uploaded}

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from threading import Thread

from app.gateway.middleware import WebSocketTokenMiddleware
from app.gateway.websocket_gateway import websocket_endpoint
from app.gateway.api_routes import router as api_router

from app.gateway.websocket_gateway import request_manager, ws_manager
from app.kafka.consumer import consume_responses
from app.kafka.config import CONSUMER_CONFIG
from app.registry import online_status_manager

# Создаем приложение FastAPI
app = FastAPI()

# Добавляем middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:3000",
        "https://kindness-event.ru/",
        "http://212.113.117.163",
        "http://212.113.117.163:80",
        "http://192.168.0.103:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(WebSocketTokenMiddleware)

app.include_router(api_router)

app.websocket("/ws")(websocket_endpoint)


def start_consumer():
    """Запускает Kafka-консьюмер в отдельном потоке."""
    array_responses = [
        'user_responses', 'identity_responses'
    ]
    consume_responses(CONSUMER_CONFIG, array_responses, request_manager)


if __name__ == "__main__":
    online_status_manager.set_ws_manager(ws_manager)
    print(f"✅ WebSocketManager передан в OnlineStatusManager")

    consumer_thread = Thread(target=start_consumer, daemon=True)
    consumer_thread.start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
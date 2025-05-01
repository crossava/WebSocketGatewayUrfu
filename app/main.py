import uvicorn
from app.gateway.websocket_gateway import app, request_manager
from app.gateway.websocket_gateway import ws_manager
from app.online_status.online_status import online_status_manager
from app.kafka.consumer import consume_responses
from app.kafka.config import CONSUMER_CONFIG
from threading import Thread


def start_consumer():
    array_responses = [
        "event_responses", "user_responses"
    ]
    consume_responses(CONSUMER_CONFIG, array_responses, request_manager)


if __name__ == "__main__":
    print(f"✅ WebSocketManager передан в OnlineStatusManager")

    # Запускаем консюмер Kafka в отдельном потоке
    consumer_thread = Thread(target=start_consumer, daemon=True)
    consumer_thread.start()

    # Запускаем FastAPI
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4000,
        ws_ping_interval=300,
        ws_ping_timeout=60 * 10
    )

import uvicorn
from app.gateway.websocket_gateway import app, request_manager
from app.gateway.websocket_gateway import ws_manager
from app.online_status.online_status import online_status_manager
from app.kafka.consumer import consume_responses
from app.kafka.config import CONSUMER_CONFIG
from threading import Thread


def start_consumer():
    array_responses = [
        "event_responses"
    ]
    consume_responses(CONSUMER_CONFIG, array_responses, request_manager)


if __name__ == "__main__":
    # ✅ Передаём ws_manager в online_status_manager перед запуском
    # online_status_manager.set_ws_manager(ws_manager)
    print(f"✅ WebSocketManager передан в OnlineStatusManager")

    # Запускаем консюмер Kafka в отдельном потоке
    consumer_thread = Thread(target=start_consumer, daemon=True)
    consumer_thread.start()

    # Запускаем FastAPI
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        ws_ping_interval=300,
        ws_ping_timeout=60 * 10
        # ssl_keyfile="/var/websocket_gateway/keys/key.pem",
        # ssl_certfile="/var/websocket_gateway/keys/cert.pem"
    )

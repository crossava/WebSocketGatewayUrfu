import json
from aiokafka import AIOKafkaProducer
from app.kafka.config import PRODUCER_CONFIG, STATUS_RESPONSE_TOPIC


class OnlineStatusManager:
    def __init__(self):
        self.online_users = set()
        self.producer = None
        self.ws_manager = None  # WebSocketManager передаём позже

    async def start_producer(self):
        """Запуск Kafka-продюсера"""
        if not self.producer:
            self.producer = AIOKafkaProducer(**PRODUCER_CONFIG)
            await self.producer.start()

    async def stop_producer(self):
        """Остановка Kafka-продюсера"""
        if self.producer:
            await self.producer.stop()

    def set_ws_manager(self, ws_manager):
        """Передаём WebSocketManager в этот класс"""
        self.ws_manager = ws_manager

    async def add_user(self, user_id):
        """Добавляет пользователя в список онлайн и отправляет обновленный список"""
        self.online_users.add(user_id)
        await self.send_status_update()

    async def remove_user(self, user_id):
        """Удаляет пользователя из списка онлайн и отправляет обновленный список"""
        self.online_users.discard(user_id)
        await self.send_status_update()

    async def send_status_update(self):
        """Отправляет список онлайн-пользователей в Kafka и WebSocket-клиентам"""
        online_users_list = list(self.online_users)
        message = json.dumps({"online_users": online_users_list})

        # 🔹 Логируем отправку сообщений
        print(f"📤 Отправляем обновленный список онлайн: {online_users_list}")

        # 🔹 Отправляем в Kafka
        if self.producer:
            await self.producer.send_and_wait(STATUS_RESPONSE_TOPIC, message.encode())

        # 🔹 Рассылаем через WebSocket
        if self.ws_manager:
            print(f"📡 Отправляем WebSocket-сообщение: {message}")
            await self.ws_manager.broadcast(message)  # 🔹 Проверяем, вызывается ли этот метод


online_status_manager = OnlineStatusManager()

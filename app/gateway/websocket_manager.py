import json

from fastapi import WebSocket
from typing import Dict
from starlette.websockets import WebSocketState, WebSocketDisconnect
from datetime import datetime


class WebSocketManager:
    """Класс для управления WebSocket-соединениями"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # Связываем user_id с WebSocket

    async def connect(self, websocket: WebSocket, user_id: str):
        """Подключает нового пользователя"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"✅ Подключён WebSocket для user_id: {user_id}")

    async def disconnect(self, user_id: str):
        websocket = self.active_connections.pop(user_id, None)
        if websocket:
            try:
                await websocket.close()
                code = getattr(websocket, "close_code", "нет кода")
                print(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')} - ❌ Отключён WebSocket для user_id: {user_id}. Код закрытия: {code}")
            except Exception as e:
                print(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')} - ⚠️ Ошибка при закрытии WebSocket для {user_id}: {e}")

    async def send_message(self, user_id: str, message: dict):
        """Отправляет сообщение конкретному пользователю по его `user_id`"""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message)
                print(f"📩 Сообщение отправлено пользователю {user_id}: {message}")
            except Exception as e:
                print(f"⚠️ Ошибка при отправке сообщения пользователю {user_id}: {e}")
                await self.disconnect(user_id)  # ✅ Если ошибка, удаляем соединение
        else:
            print(f"⚠️ Пользователь {user_id} не в сети. Сообщение не отправлено.")

    async def broadcast(self, message: str):
        """Отправляет сообщение всем подключенным WebSocket-клиентам"""
        print(f"📡 Отправляем WebSocket-сообщение всем: {message}")
        print(f"🔍 Активные соединения перед отправкой: {list(self.active_connections.keys())}")  # 👈 Новый лог

        if not self.active_connections:
            print("⚠️ Нет активных WebSocket-соединений! Сообщение не отправлено.")
            return

        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
                print(f"✅ Сообщение отправлено user_id {user_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки WebSocket user_id {user_id}: {e}")

    async def handle_pong(self, websocket: WebSocket):
        while True:
            try:
                data = await websocket.receive_json()
                if not data:
                    print("🔄 Пустое сообщение от WebSocket")
                    break

                if isinstance(data, dict) and data.get('type') == 'ping':
                    print(f"🔄 Получен pong от клиента")
            except json.JSONDecodeError:
                print("⚠️ Некорректный JSON от WebSocket")
                break
            except WebSocketDisconnect:
                print("❌ Соединение WebSocket закрыто")
                break
            except Exception as e:
                print(f"⚠️ Ошибка при получении данных от WebSocket: функция handle_pong {e}")
                break

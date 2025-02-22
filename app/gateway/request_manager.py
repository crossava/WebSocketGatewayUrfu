import asyncio
from typing import Dict
from fastapi import WebSocket


class RequestManager:
    """Класс для управления запросами WebSocket."""

    def __init__(self):
        self.active_requests: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()  # Для синхронизации в асинхронной среде

    async def add_request(self, request_id: str, websocket: WebSocket):
        async with self.lock:
            self.active_requests[request_id] = websocket
            print(
                f"[add_request] Добавлен request_id {request_id}. Активные запросы: {list(self.active_requests.keys())}")

    async def remove_request(self, request_id: str):
        async with self.lock:
            if request_id in self.active_requests:
                del self.active_requests[request_id]
                print(
                    f"[remove_request] Удалён request_id {request_id}. Активные запросы: {list(self.active_requests.keys())}")

    async def get_request(self, request_id: str):
        print(f"Попытка получить WebSocket для request_id {request_id}")
        async with self.lock:
            ws = self.active_requests.get(request_id, None)
            if ws:
                print(f"Найден WebSocket для request_id {request_id}")
            else:
                print(f"WebSocket для request_id {request_id} не найден")
            return ws

    async def get_active_requests(self):
        async with self.lock:
            return list(self.active_requests.keys())

    async def remove_disconnected(self, websocket):
        """Удаление WebSocket из активных запросов."""
        async with self.lock:
            for request_id, ws in list(self.active_requests.items()):
                if ws == websocket:
                    print(f"Удаление отключённого WebSocket: {request_id}")
                    del self.active_requests[request_id]

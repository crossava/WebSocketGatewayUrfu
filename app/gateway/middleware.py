from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import WebSocket


class WebSocketTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """Middleware для WebSocket: извлекаем access_token из cookies"""
        if request.url.path == "/ws":
            headers = dict(request.headers)
            cookies = headers.get("cookie", "")

            if cookies:
                cookies_dict = {cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies.split("; ") if
                                "=" in cookie}
                access_token = cookies_dict.get("access_token")

                if not access_token:
                    print("WebSocket отклонён: нет access_token")
                    return await call_next(request)

                request.state.access_token = access_token

        return await call_next(request)

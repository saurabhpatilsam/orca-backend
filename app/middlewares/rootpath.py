from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import BASE_PATH


class RootPathMiddleware(BaseHTTPMiddleware):
    allowed_paths = {"/", "/docs", "/redoc", "/health", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.allowed_paths or path.startswith(BASE_PATH):
            return await call_next(request)

        return Response(
            content='{"detail": "Not Found"}',
            status_code=404,
            media_type="application/json",
        )

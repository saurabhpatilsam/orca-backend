from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger):
        self.logger = logger
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Log the request
        self.logger.info(f"Request received: {request.method} {request.url}")
        response = await call_next(request)
        self.logger.info(f"Response sent: {response.status_code}")
        return response

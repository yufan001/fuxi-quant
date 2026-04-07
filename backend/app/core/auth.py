import hashlib
import secrets
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Simple token-based auth
# Default credentials: admin / lianghua2026
AUTH_USERNAME = "admin"
AUTH_PASSWORD_HASH = hashlib.sha256("lianghua2026".encode()).hexdigest()
TOKEN_EXPIRY = 86400 * 7  # 7 days

_active_tokens: dict[str, float] = {}


def verify_password(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == AUTH_PASSWORD_HASH


def create_token() -> str:
    token = secrets.token_hex(32)
    _active_tokens[token] = time.time() + TOKEN_EXPIRY
    return token


def verify_token(token: str) -> bool:
    if token not in _active_tokens:
        return False
    if time.time() > _active_tokens[token]:
        del _active_tokens[token]
        return False
    return True


class AuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/api/auth/login", "/api/auth/check"}
    STATIC_PREFIXES = ("/static/", "/modules/")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow static files and login endpoint
        if path == "/" or path == "/index.html":
            return await call_next(request)
        for prefix in self.STATIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check for API routes
        if path.startswith("/api/"):
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if not token:
                token = request.query_params.get("token", "")
            if not verify_token(token):
                return JSONResponse(status_code=401, content={"error": "未授权，请先登录"})

        return await call_next(request)

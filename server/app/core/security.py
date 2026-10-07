"""Middleware de segurança, headers e rate limiting."""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Query, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from server.app.core.auth import AuthManager


class RateLimiter:
    """Rate limiter em memória baseado em janela deslizante."""

    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        
        # Filtra timestamps fora da janela
        valid_requests = [t for t in self._requests[key] if t > cutoff]
        self._requests[key] = valid_requests
        
        if len(valid_requests) >= max_requests:
            return False
            
        self._requests[key].append(now)
        return True


# Instâncias globais de rate limit
api_limiter = RateLimiter()
login_limiter = RateLimiter()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para adicionar headers de proteção HTTP às respostas."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def get_auth_manager(request: Request) -> AuthManager:
    """Recupera instância do AuthManager a partir do app.state."""
    auth_mgr = getattr(request.app.state, "auth_manager", None)
    if not auth_mgr:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gerenciador de autenticação não inicializado"
        )
    return auth_mgr


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> str:
    """Valida token Bearer via Header ou Query Param (para SSE)."""
    if not auth_mgr.auth_enabled:
        return "admin"

    token_str = None
    if authorization and authorization.lower().startswith("bearer "):
        token_str = authorization[7:].strip()
    elif token:
        token_str = token.strip()

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Token ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = auth_mgr.verify_token(token_str)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return username

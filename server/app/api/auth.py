"""Endpoints de autenticação da API."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from server.app.core.auth import AuthManager
from server.app.core.security import get_auth_manager, get_current_user, login_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=4, max_length=128)


@router.get("/status")
async def auth_status(auth_mgr: AuthManager = Depends(get_auth_manager)):
    """Retorna se a autenticação está ativa no servidor."""
    return {
        "auth_enabled": auth_mgr.auth_enabled
    }


@router.post("/login")
async def login(
    req: LoginRequest,
    request: Request,
    auth_mgr: AuthManager = Depends(get_auth_manager)
):
    """Realiza login com usuário e senha com proteção contra força bruta."""
    client_ip = request.client.host if request.client else "unknown"
    
    # Limita tentativas de login a 10 por minuto por IP
    if not login_limiter.is_allowed(client_ip, max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login consecutivas. Aguarde 1 minuto."
        )

    token = auth_mgr.authenticate(req.username, req.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos."
        )

    return {
        "success": True,
        "token": token,
        "username": req.username,
        "auth_enabled": auth_mgr.auth_enabled
    }


@router.get("/me")
async def get_me(
    current_user: str = Depends(get_current_user),
    auth_mgr: AuthManager = Depends(get_auth_manager)
):
    """Retorna dados do usuário atualmente autenticado."""
    return {
        "username": current_user,
        "auth_enabled": auth_mgr.auth_enabled
    }


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: str = Depends(get_current_user),
    auth_mgr: AuthManager = Depends(get_auth_manager)
):
    """Permite ao usuário autenticado alterar sua própria senha."""
    if not auth_mgr.auth_enabled:
        return {"success": True, "message": "Autenticação desativada no servidor."}

    # Valida senha atual
    if not auth_mgr.authenticate(current_user, req.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha atual informada está incorreta."
        )

    if not auth_mgr.set_password(current_user, req.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve possuir pelo menos 4 caracteres."
        )

    return {
        "success": True,
        "message": "Senha alterada com sucesso."
    }

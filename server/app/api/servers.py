"""Rotas da API para gerenciamento de processos e configuração de servidores de jogos."""

from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from server.app.core.security import api_limiter, get_current_user

router = APIRouter(prefix="/api/servers", tags=["servers"])


def _get_profile_or_404(request: Request, profile_id: str):
    profile = request.app.state.profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Perfil '{profile_id}' não encontrado.")
    return profile


@router.get("/{profile_id}/status")
async def get_server_status(profile_id: str, request: Request):
    profile = _get_profile_or_404(request, profile_id)
    server_mgr = request.app.state.server_manager
    return server_mgr.get_server_status(profile)


@router.post("/{profile_id}/start")
async def start_server(
    profile_id: str,
    request: Request,
    current_user: str = Depends(get_current_user)
):
    client_ip = request.client.host if request.client else "unknown"
    if not api_limiter.is_allowed(f"srv_action:{client_ip}", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisições.")

    profile = _get_profile_or_404(request, profile_id)
    server_mgr = request.app.state.server_manager
    result = server_mgr.start_server(profile)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{profile_id}/stop")
async def stop_server(
    profile_id: str,
    request: Request,
    current_user: str = Depends(get_current_user)
):
    client_ip = request.client.host if request.client else "unknown"
    if not api_limiter.is_allowed(f"srv_action:{client_ip}", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisições.")

    profile = _get_profile_or_404(request, profile_id)
    server_mgr = request.app.state.server_manager
    result = server_mgr.stop_server(profile)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{profile_id}/restart")
async def restart_server(
    profile_id: str,
    request: Request,
    current_user: str = Depends(get_current_user)
):
    client_ip = request.client.host if request.client else "unknown"
    if not api_limiter.is_allowed(f"srv_action:{client_ip}", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisições.")

    profile = _get_profile_or_404(request, profile_id)
    server_mgr = request.app.state.server_manager
    return server_mgr.restart_server(profile)


@router.get("/{profile_id}/config")
async def get_server_config(profile_id: str, request: Request):
    profile = _get_profile_or_404(request, profile_id)
    steam_home = request.app.state.job_manager.steam_home
    cfg_file = steam_home / "games" / profile.install_dir_name / profile.config_file.filename

    exists = cfg_file.exists()
    content = cfg_file.read_text(encoding="utf-8") if exists else None

    # Valores padrão mapeados
    defaults = {f.key: f.default for f in profile.fields}

    return {
        "profile_id": profile_id,
        "filename": profile.config_file.filename,
        "exists": exists,
        "content": content,
        "defaults": defaults,
        "fields": [f.model_dump() for f in profile.fields]
    }


@router.post("/{profile_id}/config")
async def save_server_config(
    profile_id: str,
    request: Request,
    values: Dict[str, Any] = Body(...),
    current_user: str = Depends(get_current_user)
):
    profile = _get_profile_or_404(request, profile_id)
    profile_mgr = request.app.state.profile_manager
    steam_home = request.app.state.job_manager.steam_home

    try:
        validated = profile_mgr.validate_and_sanitize(profile, values)
        content = profile_mgr.generate_config_content(profile, validated)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de validação: {e}")

    # Salva arquivo de configuração no diretório do jogo
    cfg_dir = steam_home / "games" / profile.install_dir_name
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / profile.config_file.filename
    cfg_file.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "message": f"Arquivo {profile.config_file.filename} salvo com sucesso.",
        "path": str(cfg_file),
        "values": validated
    }


@router.get("/{profile_id}/logs")
async def get_server_logs(profile_id: str, request: Request, lines: int = 200):
    _get_profile_or_404(request, profile_id)
    steam_home = request.app.state.job_manager.steam_home
    log_file = steam_home / "logs" / f"{profile_id}-output.log"

    if not log_file.exists():
        return {"lines": [], "exists": False}

    try:
        all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {"lines": recent, "exists": True, "total": len(all_lines)}
    except Exception as e:
        return {"lines": [f"Erro ao ler logs: {e}"], "exists": True, "total": 0}

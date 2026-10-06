"""Rotas da API para gerenciamento e consulta de perfis de jogos."""

from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request

from server.app.profiles.models import GameProfile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_profiles(request: Request) -> List[Dict[str, Any]]:
    profile_manager = request.app.state.profile_manager
    job_manager = request.app.state.job_manager
    steam_home = job_manager.steam_home

    profiles = profile_manager.list_profiles()
    result = []
    for p in profiles:
        game_dir = steam_home / "games" / p.install_dir_name
        is_installed = (game_dir / p.executable).exists()
        has_config = (game_dir / p.config_file.filename).exists()

        result.append({
            "id": p.id,
            "name": p.name,
            "steam_app_id": p.steam_app_id,
            "install_dir_name": p.install_dir_name,
            "executable": p.executable,
            "is_installed": is_installed,
            "has_config": has_config,
            "ports_count": len(p.ports),
            "fields_count": len(p.fields),
        })
    return result


@router.get("/{profile_id}", response_model=GameProfile)
async def get_profile(profile_id: str, request: Request) -> GameProfile:
    profile_manager = request.app.state.profile_manager
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Perfil '{profile_id}' não encontrado.")
    return profile

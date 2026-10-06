"""Ponto de entrada da aplicação FastAPI do Game Server Installer."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.app.api.profiles import router as profiles_router
from server.app.api.jobs import router as jobs_router
from server.app.jobs.manager import JobManager
from server.app.profiles.manager import ProfileManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Inicialização dos serviços
    steam_home_env = os.environ.get("STEAM_HOME", "/home/steam")
    app.state.profile_manager = ProfileManager()
    app.state.job_manager = JobManager(steam_home=Path(steam_home_env))
    yield
    # Limpeza e encerramento (se necessário)


app = FastAPI(
    title="Game Server Installer API",
    description="API para instalação, configuração e streaming de servidores de jogos",
    version="1.0.0",
    lifespan=lifespan
)

# Inicialização padrão do estado da aplicação
_steam_home = Path(os.environ.get("STEAM_HOME", "/home/steam"))
app.state.profile_manager = ProfileManager()
app.state.job_manager = JobManager(steam_home=_steam_home)

# Configuração de CORS para permitir requisições locais do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rotas da API
app.include_router(profiles_router)
app.include_router(jobs_router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "game-server-installer",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    return JSONResponse({
        "name": "Game Server Installer API",
        "status": "online",
        "docs_url": "/docs",
        "profiles_url": "/api/profiles",
        "jobs_url": "/api/jobs"
    })

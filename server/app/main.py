"""Ponto de entrada da aplicação FastAPI do Game Server Installer."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.app.api.profiles import router as profiles_router
from server.app.api.jobs import router as jobs_router
from server.app.api.servers import router as servers_router
from server.app.jobs.manager import JobManager
from server.app.profiles.manager import ProfileManager
from server.app.server_manager.manager import ServerProcessManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    steam_home_env = os.environ.get("STEAM_HOME", "/home/steam")
    steam_path = Path(steam_home_env)
    app.state.profile_manager = ProfileManager()
    app.state.job_manager = JobManager(steam_home=steam_path)
    app.state.server_manager = ServerProcessManager(steam_home=steam_path)
    yield


app = FastAPI(
    title="Game Server Installer",
    description="Painel de controle e API para instalação e configuração de servidores dedicados de jogos",
    version="1.0.0",
    lifespan=lifespan
)

# Inicialização padrão do estado da aplicação
_steam_home = Path(os.environ.get("STEAM_HOME", "/home/steam"))
app.state.profile_manager = ProfileManager()
app.state.job_manager = JobManager(steam_home=_steam_home)
app.state.server_manager = ServerProcessManager(steam_home=_steam_home)

# Configuração de CORS
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
app.include_router(servers_router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "game-server-installer",
        "version": "1.0.0"
    }


# Montagem do frontend SPA estático
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"status": "frontend em construção"})
else:
    @app.get("/")
    async def root():
        return JSONResponse({
            "name": "Game Server Installer",
            "status": "online",
            "docs_url": "/docs"
        })

"""Rotas da API do Game Server Installer."""

from server.app.api.profiles import router as profiles_router
from server.app.api.jobs import router as jobs_router
from server.app.api.servers import router as servers_router

__all__ = ["profiles_router", "jobs_router", "servers_router"]

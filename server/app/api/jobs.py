"""Rotas da API para criação, consulta e streaming de tarefas assíncronas."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.app.jobs.models import Job, JobLogEntry

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class InstallJobRequest(BaseModel):
    profile_id: str
    custom_values: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.get("", response_model=List[Job])
async def list_jobs(request: Request) -> List[Job]:
    job_manager = request.app.state.job_manager
    return job_manager.list_jobs()


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str, request: Request) -> Job:
    job_manager = request.app.state.job_manager
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job


@router.get("/{job_id}/logs", response_model=List[JobLogEntry])
async def get_job_logs(job_id: str, request: Request) -> List[JobLogEntry]:
    job_manager = request.app.state.job_manager
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job_manager.get_logs(job_id)


@router.post("/install", response_model=Job, status_code=202)
async def create_install_job(request: Request, body: InstallJobRequest = Body(...)) -> Job:
    profile_manager = request.app.state.profile_manager
    job_manager = request.app.state.job_manager

    profile = profile_manager.get_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Perfil '{body.profile_id}' não encontrado.")

    # Validar valores customizados antes de aceitar o job
    if body.custom_values:
        try:
            profile_manager.validate_and_sanitize(profile, body.custom_values)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Configuração inválida: {e}")

    job = await job_manager.create_install_job(
        profile=profile,
        profile_manager=profile_manager,
        custom_values=body.custom_values
    )
    return job


@router.get("/{job_id}/stream")
async def stream_job_logs(job_id: str, request: Request) -> StreamingResponse:
    job_manager = request.app.state.job_manager
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")

    return StreamingResponse(
        job_manager.subscribe_logs(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

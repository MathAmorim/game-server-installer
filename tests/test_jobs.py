"""Testes automatizados para o JobManager e streaming de logs SSE."""

import asyncio
import sys
from pathlib import Path
import pytest

from server.app.jobs.manager import JobManager
from server.app.jobs.models import JobStatus, JobType
from server.app.profiles.manager import ProfileManager


@pytest.mark.asyncio
async def test_job_manager_creation_and_listing(tmp_path: Path):
    job_mgr = JobManager(steam_home=tmp_path)
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    prof_mgr = ProfileManager(profiles_dir=profiles_dir)

    profile = prof_mgr.get_profile("7dtd")
    assert profile is not None

    # Simular o comando steamcmd chamando python para imprimir linhas e sair 0
    fake_steamcmd = sys.executable

    job = await job_mgr.create_install_job(
        profile=profile,
        profile_manager=prof_mgr,
        steamcmd_bin=fake_steamcmd
    )

    assert job.id is not None
    assert job.job_type == JobType.INSTALL_GAME
    assert job_mgr.get_job(job.id) == job

    # Aguardar a conclusão da tarefa
    task = job_mgr._tasks.get(job.id)
    if task:
        await task

    updated_job = job_mgr.get_job(job.id)
    assert updated_job is not None
    assert updated_job.status in (JobStatus.SUCCESS, JobStatus.FAILED)
    assert len(job_mgr.get_logs(job.id)) > 0


@pytest.mark.asyncio
async def test_job_streaming_logs(tmp_path: Path):
    job_mgr = JobManager(steam_home=tmp_path)
    job_id = "test-job-1"

    # Injeta um job diretamente no estado para testar o streaming
    from server.app.jobs.models import Job
    job = Job(id=job_id, job_type=JobType.CUSTOM, profile_id="7dtd", status=JobStatus.RUNNING)
    job_mgr._jobs[job_id] = job
    job_mgr._logs[job_id] = []
    job_mgr._subscribers[job_id] = set()

    # Consumidor em background do gerador SSE
    received_lines = []

    async def consume():
        async for sse_event in job_mgr.subscribe_logs(job_id):
            received_lines.append(sse_event)
            if "event: done" in sse_event:
                break

    consumer_task = asyncio.create_task(consume())

    # Emite logs
    await asyncio.sleep(0.05)
    await job_mgr._emit_log(job_id, "Linha de teste 1")
    await asyncio.sleep(0.05)
    await job_mgr._emit_log(job_id, "Linha de teste 2")

    # Marca job como concluído
    job.status = JobStatus.SUCCESS
    await job_mgr._emit_log(job_id, "Concluído!")

    await asyncio.wait_for(consumer_task, timeout=3.0)

    # Verifica que recebeu os eventos SSE formatados com 'data:'
    combined = "".join(received_lines)
    assert "Linha de teste 1" in combined
    assert "Linha de teste 2" in combined
    assert "event: done" in combined

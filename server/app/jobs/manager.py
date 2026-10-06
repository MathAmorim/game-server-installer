"""Gerenciador assíncrono de jobs e streaming de logs via Server-Sent Events (SSE)."""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
import json

from server.app.jobs.models import Job, JobLogEntry, JobStatus, JobType
from server.app.profiles.models import GameProfile
from server.app.profiles.manager import ProfileManager


class JobManager:
    def __init__(self, steam_home: Optional[Path] = None):
        self.steam_home = Path(steam_home or os.environ.get("STEAM_HOME", "/home/steam"))
        self._jobs: Dict[str, Job] = {}
        self._logs: Dict[str, List[JobLogEntry]] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Job]:
        return list(self._jobs.values())

    def get_logs(self, job_id: str) -> List[JobLogEntry]:
        return self._logs.get(job_id, [])

    async def create_install_job(
        self,
        profile: GameProfile,
        profile_manager: ProfileManager,
        custom_values: Optional[Dict[str, Any]] = None,
        steamcmd_bin: Optional[str] = None
    ) -> Job:
        """
        Cria e enfileira uma tarefa assíncrona para instalar/atualizar um servidor de jogo via SteamCMD.
        """
        job_id = str(uuid.uuid4())[:8]
        job = Job(
            id=job_id,
            job_type=JobType.INSTALL_GAME,
            profile_id=profile.id,
            status=JobStatus.PENDING,
            metadata={
                "game_name": profile.name,
                "steam_app_id": profile.steam_app_id,
            }
        )

        async with self._lock:
            self._jobs[job_id] = job
            self._logs[job_id] = []
            self._subscribers[job_id] = set()

        # Inicia a execução em background
        task = asyncio.create_task(
            self._run_install_task(job, profile, profile_manager, custom_values, steamcmd_bin)
        )
        self._tasks[job_id] = task
        return job

    async def _emit_log(self, job_id: str, text: str) -> None:
        """Registra a linha de log e envia para todos os assinantes conectados."""
        entry = JobLogEntry(text=text)
        if job_id in self._logs:
            self._logs[job_id].append(entry)

        subscribers = self._subscribers.get(job_id, set())
        for queue in list(subscribers):
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    async def _run_install_task(
        self,
        job: Job,
        profile: GameProfile,
        profile_manager: ProfileManager,
        custom_values: Optional[Dict[str, Any]],
        steamcmd_bin: Optional[str]
    ) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()
        await self._emit_log(job.id, f"==> Iniciando job #{job.id}: Instalação de {profile.name} (App ID {profile.steam_app_id})")

        install_dir = self.steam_home / "games" / profile.install_dir_name
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = f"Falha ao criar diretório do jogo: {e}"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            await self._emit_log(job.id, f"[ERRO] {job.error}")
            return

        bin_path = steamcmd_bin or os.environ.get("STEAMCMD_BIN", "steamcmd")

        # Argumentos estritos para execução do SteamCMD (sem interpolação shell)
        cmd = [
            bin_path,
            "+force_install_dir",
            str(install_dir.resolve()),
            "+login",
            "anonymous",
            "+app_update",
            str(profile.steam_app_id),
            "validate",
            "+quit"
        ]

        await self._emit_log(job.id, f"==> Diretório de destino: {install_dir}")
        await self._emit_log(job.id, f"==> Executando comando: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Transmite stdout/stderr linha a linha em tempo real
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                    await self._emit_log(job.id, decoded_line)

            returncode = await process.wait()
            job.returncode = returncode

            if returncode == 0:
                await self._emit_log(job.id, "==> SteamCMD concluído com sucesso!")
                # Gerar configuração se necessário
                cfg_path = install_dir / profile.config_file.filename
                if not cfg_path.exists() or custom_values:
                    await self._emit_log(job.id, f"==> Gerando arquivo de configuração {profile.config_file.filename}...")
                    vals = profile_manager.validate_and_sanitize(profile, custom_values or {})
                    cfg_content = profile_manager.generate_config_content(profile, vals)
                    cfg_path.write_text(cfg_content, encoding="utf-8")
                    await self._emit_log(job.id, f"[OK] Configuração {profile.config_file.filename} gerada.")

                job.status = JobStatus.SUCCESS
                await self._emit_log(job.id, f"[SUCESSO] Instalação de {profile.name} concluída!")
            else:
                job.status = JobStatus.FAILED
                job.error = f"SteamCMD encerrou com código de saída {returncode}"
                await self._emit_log(job.id, f"[ERRO] {job.error}")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            await self._emit_log(job.id, f"[ERRO FATAL] Exceção durante execução: {e}")

        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()

    async def subscribe_logs(self, job_id: str) -> AsyncGenerator[str, None]:
        """
        Gera eventos formatados para Server-Sent Events (SSE).
        Envia primeiro os logs do buffer acumulado e depois os novos eventos ao vivo.
        """
        queue: asyncio.Queue[Optional[JobLogEntry]] = asyncio.Queue(maxsize=1000)

        # Envia histórico de logs acumulados
        existing_logs = self.get_logs(job_id)
        for log in existing_logs:
            data = json.dumps({"timestamp": log.timestamp, "text": log.text})
            yield f"data: {data}\n\n"

        # Se o job já finalizou, encerra o stream
        job = self.get_job(job_id)
        if job and job.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED):
            yield f"event: done\ndata: {json.dumps({'status': job.status.value})}\n\n"
            return

        if job_id not in self._subscribers:
            self._subscribers[job_id] = set()
        self._subscribers[job_id].add(queue)

        try:
            while True:
                # Aguarda nova linha de log ou timeout para keepalive
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if entry is None:
                        break
                    data = json.dumps({"timestamp": entry.timestamp, "text": entry.text})
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Envia ping de keepalive para manter a conexão aberta no browser
                    yield ": keepalive\n\n"

                # Verifica se o job finalizou
                curr_job = self.get_job(job_id)
                if curr_job and curr_job.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED):
                    # Aguarda esvaziar a fila antes de enviar done
                    while not queue.empty():
                        rem = queue.get_nowait()
                        if rem:
                            d = json.dumps({"timestamp": rem.timestamp, "text": rem.text})
                            yield f"data: {d}\n\n"
                    yield f"event: done\ndata: {json.dumps({'status': curr_job.status.value})}\n\n"
                    break

        finally:
            if job_id in self._subscribers and queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)

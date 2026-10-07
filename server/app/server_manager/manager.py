"""Gerenciador de ciclo de vida de processos de servidores de jogos (start/stop/restart/status)."""

import asyncio
import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from server.app.profiles.models import GameProfile


class ServerProcessManager:
    def __init__(self, steam_home: Optional[Path] = None):
        self.steam_home = Path(steam_home or os.environ.get("STEAM_HOME", "/home/steam"))
        self._processes: Dict[str, subprocess.Popen] = {}
        self._started_at: Dict[str, str] = {}
        self._pid_files_dir = self.steam_home / "logs"
        self._pid_files_dir.mkdir(parents=True, exist_ok=True)

    def _get_pid_file(self, profile_id: str) -> Path:
        return self._pid_files_dir / f"{profile_id}.pid"

    def is_running(self, profile_id: str) -> bool:
        """Verifica se o servidor de jogo está em execução via processo ou arquivo PID."""
        # Processo ativo na instância atual
        proc = self._processes.get(profile_id)
        if proc:
            if proc.poll() is None:
                return True
            else:
                del self._processes[profile_id]

        # Verificar se existe arquivo PID salvo
        pid_file = self._get_pid_file(profile_id)
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # Enviar sinal 0 para verificar existência do processo
                os.kill(pid, 0)
                return True
            except (ValueError, OSError):
                # Processo não existe mais, remover arquivo PID stale
                pid_file.unlink(missing_ok=True)
                return False
        return False

    def get_server_status(self, profile: GameProfile) -> Dict[str, Any]:
        """Retorna informações de status do servidor de jogo."""
        running = self.is_running(profile.id)
        game_dir = self.steam_home / "games" / profile.install_dir_name
        is_installed = (game_dir / profile.executable).exists()
        has_config = (game_dir / profile.config_file.filename).exists()

        pid = None
        if running:
            proc = self._processes.get(profile.id)
            if proc:
                pid = proc.pid
            else:
                pid_file = self._get_pid_file(profile.id)
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                    except ValueError:
                        pass

        return {
            "profile_id": profile.id,
            "game_name": profile.name,
            "running": running,
            "is_installed": is_installed,
            "has_config": has_config,
            "pid": pid,
            "started_at": self._started_at.get(profile.id) if running else None,
            "install_dir": str(game_dir),
            "ports": [p.model_dump() for p in profile.ports]
        }

    def start_server(self, profile: GameProfile) -> Dict[str, Any]:
        """Inicia o servidor de jogo com argumentos e caminhos seguros."""
        if self.is_running(profile.id):
            return {"success": False, "message": "O servidor já está em execução."}

        game_dir = self.steam_home / "games" / profile.install_dir_name
        exec_path = game_dir / profile.executable

        if not exec_path.exists():
            return {
                "success": False,
                "message": f"Executável '{profile.executable}' não encontrado. O jogo está instalado?"
            }

        # Garantir permissão de execução
        try:
            exec_path.chmod(0o755)
        except OSError:
            pass

        cmd = [str(exec_path.resolve())] + list(profile.start_arguments)
        log_file_path = self._pid_files_dir / f"{profile.id}-output.log"
        log_out = open(log_file_path, "a", encoding="utf-8")

        # Inicia processo isolado em novo grupo de processos
        proc = subprocess.Popen(
            cmd,
            cwd=str(game_dir.resolve()),
            stdout=log_out,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None
        )

        self._processes[profile.id] = proc
        self._started_at[profile.id] = datetime.now(timezone.utc).isoformat()

        # Salvar arquivo PID
        pid_file = self._get_pid_file(profile.id)
        pid_file.write_text(str(proc.pid))

        return {
            "success": True,
            "message": f"Servidor {profile.name} iniciado com sucesso.",
            "pid": proc.pid
        }

    def stop_server(self, profile: GameProfile, timeout_sec: int = 15) -> Dict[str, Any]:
        """Para o servidor de jogo de forma graciosa para salvar o estado do mundo."""
        if not self.is_running(profile.id):
            return {"success": False, "message": "O servidor não está em execução."}

        pid = None
        proc = self._processes.get(profile.id)
        if proc:
            pid = proc.pid
        else:
            pid_file = self._get_pid_file(profile.id)
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                except ValueError:
                    pass

        if not pid:
            return {"success": False, "message": "PID do servidor não encontrado."}

        # Enviar sinal SIGTERM gracioso para salvar o jogo
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

        # Aguardar encerramento gracioso
        if proc:
            try:
                proc.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                # Forçar SIGKILL se não encerrou a tempo
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    else:
                        os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            self._processes.pop(profile.id, None)

        self._get_pid_file(profile.id).unlink(missing_ok=True)
        self._started_at.pop(profile.id, None)

        return {"success": True, "message": f"Servidor {profile.name} finalizado."}

    def restart_server(self, profile: GameProfile) -> Dict[str, Any]:
        """Reinicia o servidor de jogo."""
        self.stop_server(profile)
        return self.start_server(profile)

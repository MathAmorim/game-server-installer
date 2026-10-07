"""Módulo de autenticação e segurança do Game Server Installer."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Dict, Optional, Tuple


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = 100_000) -> str:
    """Gera hash PBKDF2-HMAC-SHA256 seguro com salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica senha contra hash PBKDF2."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected_key = base64.b64decode(parts[3].encode("ascii"))
        computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(expected_key, computed_key)
    except Exception:
        return False


def create_token(username: str, secret_key: str, expires_in_seconds: int = 86400 * 7) -> str:
    """Cria um token assinado e com expiração (stateless)."""
    expires_at = int(time.time()) + expires_in_seconds
    payload_str = f"{username}:{expires_at}"
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode("utf-8")).decode("ascii").rstrip("=")
    
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"


def verify_token(token: str, secret_key: str) -> Optional[str]:
    """Valida um token assinado e retorna o username caso válido."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts[0], parts[1]
        
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        # Corrige padding base64
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_str = base64.urlsafe_b64decode((payload_b64 + padding).encode("ascii")).decode("utf-8")
        
        username, expires_at_str = payload_str.split(":", 1)
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return None
        
        return username
    except Exception:
        return None


class AuthManager:
    """Gerenciador de autenticação e credenciais do painel."""

    def __init__(self, auth_file: Optional[Path] = None, steam_home: Optional[Path] = None):
        if auth_file:
            self.auth_file = auth_file
        else:
            base_home = steam_home or Path(os.environ.get("STEAM_HOME", "/home/steam"))
            self.auth_file = base_home / ".gsi" / "auth.json"

        # Flag de desativação opcional via ambiente
        env_auth_enabled = os.environ.get("GSI_AUTH_ENABLED", "").lower()
        self._force_disabled = env_auth_enabled in ("false", "0", "no")

        self._data: Dict = {}
        self._last_mtime: float = 0.0
        self.load_or_init()

    def reload_if_changed(self) -> None:
        """Recarrega os dados do disco caso o arquivo tenha sido modificado externamente."""
        if not self.auth_file.exists():
            return
        try:
            mtime = self.auth_file.stat().st_mtime
            if mtime > self._last_mtime:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._last_mtime = mtime
        except Exception:
            pass

    @property
    def auth_enabled(self) -> bool:
        if self._force_disabled:
            return False
        self.reload_if_changed()
        return self._data.get("auth_enabled", True)

    @property
    def secret_key(self) -> str:
        self.reload_if_changed()
        return self._data.get("secret_key", "gsi-default-secret-key-change-me")

    def load_or_init(self) -> None:
        """Carrega configuração de autenticação existente ou inicializa padrão seguro."""
        if self.auth_file.exists():
            try:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._last_mtime = self.auth_file.stat().st_mtime
                return
            except Exception:
                pass

        # Inicializa arquivo com usuário admin padrão
        self._init_defaults()

    def _init_defaults(self, initial_password: Optional[str] = None) -> Tuple[str, str]:
        """Inicializa credenciais padrão no arquivo com permissão restrita."""
        username = "admin"
        password = initial_password or os.environ.get("GSI_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        secret_key = secrets.token_hex(32)

        self._data = {
            "auth_enabled": True,
            "secret_key": secret_key,
            "users": {
                username: {
                    "password_hash": hash_password(password),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        }
        self.save()
        return username, password

    def save(self) -> None:
        """Salva arquivo de autenticação com permissão chmod 600 em sistemas POSIX."""
        self.auth_file.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                os.chmod(self.auth_file.parent, 0o700)
            except Exception:
                pass

        temp_file = self.auth_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

        if os.name != "nt":
            try:
                os.chmod(temp_file, 0o600)
            except Exception:
                pass

        temp_file.replace(self.auth_file)
        if self.auth_file.exists():
            try:
                self._last_mtime = self.auth_file.stat().st_mtime
            except Exception:
                pass

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Autentica usuário e retorna token de sessão se válido."""
        self.reload_if_changed()
        if not self.auth_enabled:
            return create_token(username or "admin", self.secret_key)

        users = self._data.get("users", {})
        user_info = users.get(username)
        if not user_info:
            return None

        pwd_hash = user_info.get("password_hash", "")
        if verify_password(password, pwd_hash):
            return create_token(username, self.secret_key)
        return None

    def verify_token(self, token: str) -> Optional[str]:
        """Verifica token de acesso."""
        self.reload_if_changed()
        if not self.auth_enabled:
            return "admin"
        return verify_token(token, self.secret_key)

    def set_password(self, username: str, new_password: str) -> bool:
        """Atualiza ou cria a senha de um usuário."""
        if not new_password or len(new_password.strip()) < 4:
            return False
        
        users = self._data.setdefault("users", {})
        users[username] = {
            "password_hash": hash_password(new_password),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save()
        return True

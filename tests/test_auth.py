"""Testes automatizados para autenticação, tokens, hashing e rate limiting."""

import time
import pytest
from fastapi.testclient import TestClient

from server.app.core.auth import (
    AuthManager,
    create_token,
    hash_password,
    verify_password,
    verify_token,
)
from server.app.core.security import RateLimiter
from server.app.main import app

client = TestClient(app)


def test_password_hashing():
    pwd = "MinhaSenhaForte123!"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("SenhaErrada", hashed) is False
    assert verify_password("", hashed) is False


def test_token_creation_and_verification():
    secret = "secret-key-test-12345"
    token = create_token("admin", secret, expires_in_seconds=3600)
    assert "." in token

    # Token válido
    username = verify_token(token, secret)
    assert username == "admin"

    # Chave secreta diferente deve falhar
    assert verify_token(token, "wrong-secret") is None

    # Token adulterado deve falhar
    tampered = token[:-2] + "xx"
    assert verify_token(tampered, secret) is None

    # Token expirado
    expired_token = create_token("admin", secret, expires_in_seconds=-10)
    assert verify_token(expired_token, secret) is None


def test_auth_manager(tmp_path):
    auth_file = tmp_path / "auth.json"
    mgr = AuthManager(auth_file=auth_file)
    assert mgr.auth_enabled is True
    assert "admin" in mgr._data["users"]

    # Definir nova senha
    assert mgr.set_password("admin", "nova_senha_teste") is True
    assert mgr.set_password("admin", "12") is False  # Muito curta

    # Autenticar com a nova senha
    token = mgr.authenticate("admin", "nova_senha_teste")
    assert token is not None
    assert mgr.verify_token(token) == "admin"

    # Senha incorreta
    assert mgr.authenticate("admin", "senha_incorreta") is None


def test_api_auth_endpoints():
    auth_mgr = app.state.auth_manager
    auth_mgr.set_password("admin", "adminPassTest123")

    # 1. Status da autenticação
    status_res = client.get("/api/auth/status")
    assert status_res.status_code == 200
    assert "auth_enabled" in status_res.json()

    # 2. Login com falha
    fail_res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert fail_res.status_code == 401

    # 3. Login com sucesso
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "adminPassTest123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    assert token is not None

    # 4. GET /me com token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"

    # 5. GET /me sem token (deve falhar 401)
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401


def test_rate_limiter():
    limiter = RateLimiter()
    ip = "192.168.1.100"

    # Limite de 3 requisições
    assert limiter.is_allowed(ip, max_requests=3, window_seconds=10) is True
    assert limiter.is_allowed(ip, max_requests=3, window_seconds=10) is True
    assert limiter.is_allowed(ip, max_requests=3, window_seconds=10) is True
    assert limiter.is_allowed(ip, max_requests=3, window_seconds=10) is False

    # Outro IP continua liberado
    assert limiter.is_allowed("192.168.1.101", max_requests=3, window_seconds=10) is True

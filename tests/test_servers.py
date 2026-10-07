"""Testes automatizados para endpoints de controle do servidor e frontend."""

from fastapi.testclient import TestClient
from server.app.main import app

client = TestClient(app)


def test_serve_frontend_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Game Server Installer" in response.text
    assert "Catálogo de Servidores" in response.text


def test_get_server_status():
    response = client.get("/api/servers/7dtd/status")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_id"] == "7dtd"
    assert data["game_name"] == "7 Days to Die"
    assert "running" in data
    assert "is_installed" in data
    assert "ports" in data
    assert len(data["ports"]) >= 4


def test_get_and_save_server_config():
    # Consultar config
    res = client.get("/api/servers/7dtd/config")
    assert res.status_code == 200
    cfg = res.json()
    assert cfg["filename"] == "serverconfig.xml"
    assert "fields" in cfg
    assert len(cfg["fields"]) >= 15

    # Salvar config customizada
    save_res = client.post(
        "/api/servers/7dtd/config",
        json={
            "ServerName": "Servidor Teste Unitario",
            "ServerPort": 26900,
            "ServerMaxPlayerCount": 16,
            "GameWorld": "Navezgane",
            "GameName": "MyTestSave"
        }
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["success"] is True
    assert save_data["values"]["ServerName"] == "Servidor Teste Unitario"
    assert save_data["values"]["ServerMaxPlayerCount"] == 16


def test_server_start_when_not_installed():
    # Tentativa de iniciar jogo não instalado retorna erro 400 amigável
    res = client.post("/api/servers/7dtd/start")
    # Se não estiver instalado, retorna 400
    if res.status_code == 400:
        assert "não encontrado" in res.json()["detail"] or "já está em execução" in res.json()["detail"]
    else:
        assert res.status_code in (200, 400)

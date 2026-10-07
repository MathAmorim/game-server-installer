from fastapi.testclient import TestClient
from server.app.core.auth import create_token
from server.app.main import app

client = TestClient(app)


def get_auth_headers():
    auth_mgr = app.state.auth_manager
    token = create_token("admin", auth_mgr.secret_key)
    return {"Authorization": f"Bearer {token}"}


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "game-server-installer"


def test_api_list_profiles():
    response = client.get("/api/profiles")
    assert response.status_code == 200
    profiles = response.json()
    assert isinstance(profiles, list)
    assert len(profiles) >= 1

    profile_7dtd = next((p for p in profiles if p["id"] == "7dtd"), None)
    assert profile_7dtd is not None
    assert profile_7dtd["name"] == "7 Days to Die"
    assert profile_7dtd["steam_app_id"] == 294420
    assert "is_installed" in profile_7dtd


def test_api_get_profile_detail():
    response = client.get("/api/profiles/7dtd")
    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == "7dtd"
    assert profile["config_file"]["filename"] == "serverconfig.xml"
    assert len(profile["fields"]) >= 15
    assert len(profile["ports"]) >= 4


def test_api_get_profile_not_found():
    response = client.get("/api/profiles/non_existent_game")
    assert response.status_code == 404


def test_api_create_job_unauthorized():
    # Sem header de autenticação deve retornar 401
    response = client.post("/api/jobs/install", json={"profile_id": "7dtd"})
    assert response.status_code == 401


def test_api_create_job_invalid_profile():
    response = client.post(
        "/api/jobs/install",
        json={"profile_id": "invalid_game"},
        headers=get_auth_headers()
    )
    assert response.status_code == 404


def test_api_create_job_invalid_custom_values():
    response = client.post(
        "/api/jobs/install",
        json={
            "profile_id": "7dtd",
            "custom_values": {
                "ServerPort": 999999  # Porta fora do intervalo
            }
        },
        headers=get_auth_headers()
    )
    assert response.status_code == 400
    assert "Configuração inválida" in response.json()["detail"]


def test_api_create_and_get_job():
    response = client.post(
        "/api/jobs/install",
        json={"profile_id": "7dtd"},
        headers=get_auth_headers()
    )
    assert response.status_code == 202
    job_data = response.json()
    job_id = job_data["id"]
    assert job_data["status"] in ("pending", "running", "failed", "success")

    # Consultar status do job
    get_res = client.get(f"/api/jobs/{job_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == job_id

    # Consultar logs do job
    logs_res = client.get(f"/api/jobs/{job_id}/logs")
    assert logs_res.status_code == 200
    assert isinstance(logs_res.json(), list)

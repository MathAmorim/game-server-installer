"""Testes da interface de linha de comando."""

import subprocess
import sys


def test_cli_validate_profile():
    res = subprocess.run(
        [sys.executable, "-m", "server.app.cli", "validate-profile", "7dtd"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "7 Days to Die" in res.stdout
    assert "294420" in res.stdout


def test_cli_generate_config():
    res = subprocess.run(
        [sys.executable, "-m", "server.app.cli", "generate-config", "7dtd"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "<ServerSettings>" in res.stdout
    assert 'name="ServerPort"' in res.stdout

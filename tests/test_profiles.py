"""Testes automatizados para validação de perfis e geração do serverconfig.xml."""

import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from server.app.profiles.manager import ProfileManager, ProfileValidationError


@pytest.fixture
def manager() -> ProfileManager:
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    return ProfileManager(profiles_dir=profiles_dir)


def test_load_7dtd_profile(manager: ProfileManager):
    """Garante que o perfil do 7 Days to Die é carregado e possui os campos exigidos."""
    profile = manager.get_profile("7dtd")
    assert profile is not None
    assert profile.name == "7 Days to Die"
    assert profile.steam_app_id == 294420
    assert profile.anonymous_login is True
    assert profile.executable == "startserver.sh"
    assert "-configfile=serverconfig.xml" in profile.start_arguments
    assert profile.config_file.filename == "serverconfig.xml"
    assert profile.config_file.format == "xml_properties"

    # Verificar portas principais
    port_numbers = [p.port for p in profile.ports]
    assert 26900 in port_numbers
    assert 26901 in port_numbers
    assert 26902 in port_numbers
    assert 26903 in port_numbers


def test_default_values_validation(manager: ProfileManager):
    """Valida se os valores padrões do perfil geram uma configuração válida."""
    profile = manager.get_profile("7dtd")
    assert profile is not None

    validated = manager.validate_and_sanitize(profile, {})
    assert validated["ServerName"] == "My 7 Days to Die Dedicated Server"
    assert validated["ServerPort"] == 26900
    assert validated["ServerMaxPlayerCount"] == 8
    assert validated["GameWorld"] == "Navezgane"
    assert validated["EACEnabled"] is True

    # Gera XML e valida com o parser oficial de XML
    xml_content = manager.generate_config_content(profile, validated)
    root = ET.fromstring(xml_content)
    assert root.tag == "ServerSettings"

    # Verificar propriedades geradas
    properties = {elem.attrib["name"]: elem.attrib["value"] for elem in root.findall("property")}
    assert properties["ServerName"] == "My 7 Days to Die Dedicated Server"
    assert properties["ServerPort"] == "26900"
    assert properties["EACEnabled"] == "true"


def test_validation_rejects_invalid_port(manager: ProfileManager):
    """Garante que portas inválidas (fora do range 1024-65535) são rejeitadas."""
    profile = manager.get_profile("7dtd")
    assert profile is not None

    with pytest.raises(ProfileValidationError, match="no mínimo 1024"):
        manager.validate_and_sanitize(profile, {"ServerPort": 80})

    with pytest.raises(ProfileValidationError, match="no máximo 65535"):
        manager.validate_and_sanitize(profile, {"ServerPort": 70000})


def test_validation_rejects_invalid_select_option(manager: ProfileManager):
    """Garante que opções fora da lista permitida são rejeitadas."""
    profile = manager.get_profile("7dtd")
    assert profile is not None

    with pytest.raises(ProfileValidationError, match="Valor inválido '99'"):
        manager.validate_and_sanitize(profile, {"GameDifficulty": "99"})


def test_path_traversal_protection(manager: ProfileManager):
    """Garante que tentativas de path traversal em nomes de saves são bloqueadas."""
    profile = manager.get_profile("7dtd")
    assert profile is not None

    with pytest.raises(ProfileValidationError, match="não pode conter barras"):
        manager.validate_and_sanitize(profile, {"GameName": "../../etc/passwd"})

    with pytest.raises(ProfileValidationError, match="não pode conter barras"):
        manager.validate_and_sanitize(profile, {"GameName": "save/subfolder"})


def test_xml_injection_sanitization(manager: ProfileManager):
    """Garante que caracteres especiais (<, >, \", &) sofrem escape e não quebram o XML."""
    profile = manager.get_profile("7dtd")
    assert profile is not None

    malicious_name = 'My Server & "Test" <script>alert(1)</script>'
    validated = manager.validate_and_sanitize(profile, {"ServerName": malicious_name})
    xml_content = manager.generate_config_content(profile, validated)

    # Não pode conter tags injetadas desescapadas
    assert "<script>" not in xml_content

    # O XML resultante deve ser válido e parseável
    root = ET.fromstring(xml_content)
    properties = {elem.attrib["name"]: elem.attrib["value"] for elem in root.findall("property")}
    assert properties["ServerName"] == malicious_name

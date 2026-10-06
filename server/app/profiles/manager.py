"""Gerenciador e validador de perfis de jogos e geração de arquivos de configuração."""

import os
import re
import xml.sax.saxutils as saxutils
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from server.app.profiles.models import GameProfile, ConfigField


class ProfileValidationError(Exception):
    """Exceção levantada em caso de falha de validação dos valores de configuração."""
    pass


class ProfileManager:
    def __init__(self, profiles_dir: Optional[Path] = None):
        if profiles_dir is None:
            # Padrão: pasta 'profiles' na raiz do projeto
            self.profiles_dir = Path(__file__).resolve().parent.parent.parent.parent / "profiles"
        else:
            self.profiles_dir = Path(profiles_dir)
        self._profiles: Dict[str, GameProfile] = {}
        self.reload_profiles()

    def reload_profiles(self) -> None:
        """Carrega e valida todos os perfis YAML disponíveis no diretório de perfis."""
        self._profiles.clear()
        if not self.profiles_dir.exists():
            return

        for file_path in self.profiles_dir.glob("*.yaml"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                profile = GameProfile(**data)
                self._profiles[profile.id] = profile

    def get_profile(self, profile_id: str) -> Optional[GameProfile]:
        """Obtém um perfil de jogo por ID."""
        return self._profiles.get(profile_id)

    def list_profiles(self) -> List[GameProfile]:
        """Lista todos os perfis carregados."""
        return list(self._profiles.values())

    def validate_and_sanitize(self, profile: GameProfile, user_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida e sanitiza os valores fornecidos pelo usuário contra o esquema do perfil.
        Garante integridade de tipos, restrições numéricas/textuais e segurança contra injeções.
        """
        validated: Dict[str, Any] = {}
        fields_by_key: Dict[str, ConfigField] = {f.key: f for f in profile.fields}

        for field in profile.fields:
            raw_value = user_values.get(field.key, field.default)

            # Campo obrigatório vazio
            if field.required and (raw_value is None or raw_value == ""):
                raise ProfileValidationError(f"O campo '{field.label}' ({field.key}) é obrigatório.")

            if raw_value is None:
                validated[field.key] = field.default
                continue

            # Validação e coerção por tipo
            if field.type == "integer":
                try:
                    val_int = int(raw_value)
                except (ValueError, TypeError):
                    raise ProfileValidationError(f"O campo '{field.label}' deve ser um número inteiro válido.")
                if field.min is not None and val_int < field.min:
                    raise ProfileValidationError(f"O campo '{field.label}' deve ser no mínimo {field.min}.")
                if field.max is not None and val_int > field.max:
                    raise ProfileValidationError(f"O campo '{field.label}' deve ser no máximo {field.max}.")
                validated[field.key] = val_int

            elif field.type == "boolean":
                if isinstance(raw_value, bool):
                    validated[field.key] = raw_value
                elif isinstance(raw_value, str):
                    val_lower = raw_value.strip().lower()
                    if val_lower in ("true", "1", "yes", "on"):
                        validated[field.key] = True
                    elif val_lower in ("false", "0", "no", "off"):
                        validated[field.key] = False
                    else:
                        raise ProfileValidationError(f"O campo '{field.label}' deve ser um booleano (true/false).")
                else:
                    validated[field.key] = bool(raw_value)

            elif field.type == "select":
                str_val = str(raw_value).strip()
                if field.options:
                    valid_values = {opt.value for opt in field.options}
                    if str_val not in valid_values:
                        raise ProfileValidationError(
                            f"Valor inválido '{str_val}' para o campo '{field.label}'. Opções válidas: {sorted(valid_values)}"
                        )
                validated[field.key] = str_val

            elif field.type in ("string", "password"):
                str_val = str(raw_value).strip()
                # Proteção contra injeção de quebra de linha maliciosa e caracteres de controle
                if any(ord(c) < 32 and c not in ("\t", "\n", "\r") for c in str_val):
                    raise ProfileValidationError(f"O campo '{field.label}' contém caracteres de controle inválidos.")

                # Bloqueio de path traversal se o campo for nome de save ou arquivo
                if field.key in ("GameName", "GameWorld"):
                    if "/" in str_val or "\\" in str_val or ".." in str_val:
                        raise ProfileValidationError(f"O campo '{field.label}' não pode conter barras ou '..'.")

                if field.min_length is not None and len(str_val) < field.min_length:
                    raise ProfileValidationError(
                        f"O campo '{field.label}' deve ter pelo menos {field.min_length} caracteres."
                    )
                if field.max_length is not None and len(str_val) > field.max_length:
                    raise ProfileValidationError(
                        f"O campo '{field.label}' deve ter no máximo {field.max_length} caracteres."
                    )
                validated[field.key] = str_val

            else:
                validated[field.key] = raw_value

        return validated

    def generate_config_content(self, profile: GameProfile, validated_values: Dict[str, Any]) -> str:
        """
        Gera o conteúdo textual do arquivo de configuração no formato especificado pelo perfil.
        Aplica escape contra injeção de XML/tags maliciosas.
        """
        if profile.config_file.format == "xml_properties":
            return self._generate_xml_properties(profile, validated_values)
        else:
            raise NotImplementedError(f"Formato '{profile.config_file.format}' não suportado.")

    def _generate_xml_properties(self, profile: GameProfile, values: Dict[str, Any]) -> str:
        """
        Gera formato XML padrão para 7 Days to Die:
        <ServerSettings>
          <property name="ServerName" value="My Server" />
          ...
        </ServerSettings>
        """
        lines = [
            '<?xml version="1.0"?>',
            '<!-- Gerado automaticamente pelo Game Server Installer -->',
            '<ServerSettings>'
        ]

        for field in profile.fields:
            val = values.get(field.key, field.default)
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            else:
                val_str = str(val)

            # Sanitização e escape contra injeção de XML
            safe_name = saxutils.escape(field.key, {'"': "&quot;"})
            safe_val = saxutils.escape(val_str, {'"': "&quot;"})

            lines.append(f'  <property name="{safe_name}" value="{safe_val}" />')

        lines.append('</ServerSettings>')
        lines.append('')
        return "\n".join(lines)

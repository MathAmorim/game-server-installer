"""Modelos de dados declarativos para perfis de jogos e campos de configuração."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class PortDefinition(BaseModel):
    port: int = Field(..., ge=1, le=65535)
    protocol: Literal["TCP", "UDP", "TCP/UDP"]
    description: str
    optional: bool = False


class SelectOption(BaseModel):
    label: str
    value: str


class ConfigField(BaseModel):
    key: str
    label: str
    type: Literal["string", "integer", "boolean", "password", "select"]
    default: Any
    required: bool = False
    min: Optional[int] = None
    max: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    options: Optional[List[SelectOption]] = None
    description: str = ""


class ConfigFileDefinition(BaseModel):
    filename: str
    format: Literal["xml_properties", "ini", "json"]

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("O nome do arquivo não pode conter caminhos relativos ou barras.")
        return v


class GameProfile(BaseModel):
    id: str
    name: str
    steam_app_id: int = Field(..., gt=0)
    anonymous_login: bool = True
    install_dir_name: str
    executable: str
    start_arguments: List[str] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)
    ports: List[PortDefinition] = Field(default_factory=list)
    config_file: ConfigFileDefinition
    fields: List[ConfigField] = Field(default_factory=list)

    @field_validator("install_dir_name", "id")
    @classmethod
    def validate_safe_id(cls, v: str) -> str:
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError(f"Identificador inválido '{v}': caracteres proibidos.")
        return v

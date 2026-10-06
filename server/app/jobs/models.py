"""Modelos de dados para o gerenciamento de tarefas assíncronas (jobs)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    INSTALL_GAME = "install_game"
    UPDATE_GAME = "update_game"
    VALIDATE_GAME = "validate_game"
    CUSTOM = "custom"


class JobLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    text: str


class Job(BaseModel):
    id: str
    job_type: JobType
    profile_id: str
    status: JobStatus = JobStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    returncode: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

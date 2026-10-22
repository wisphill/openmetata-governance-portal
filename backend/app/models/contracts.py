from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Identity(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None


class RoleSummary(BaseModel):
    direct: list[dict[str, Any]] = Field(default_factory=list)
    inherited: list[dict[str, Any]] = Field(default_factory=list)


class MeResponse(BaseModel):
    identity: Identity
    teams: list[dict[str, Any]] = Field(default_factory=list)
    roles: RoleSummary = Field(default_factory=RoleSummary)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    is_admin: bool = False
    source: str = "openmetadata"


class Task(BaseModel):
    id: str
    type: str | None = None
    status: str | None = None
    assignee: str | None = None
    entity: dict[str, Any] | None = None
    created_at: datetime | None = None
    due_at: datetime | None = None
    requester: str | None = None
    link: str | None = None


class TaskPage(BaseModel):
    items: list[Task]
    page: int
    page_size: int
    total: int | None = None


class QueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10_000)
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

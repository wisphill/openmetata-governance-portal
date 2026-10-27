from datetime import datetime
from typing import Annotated, Any, Literal

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
    request_id: str | None = None
    type: str | None = None
    status: str | None = None
    assignee: str | None = None
    assignees: list[str] = Field(default_factory=list)
    entity: dict[str, Any] | None = None
    created_at: datetime | None = None
    due_at: datetime | None = None
    requester: str | None = None
    reason: str | None = None
    link: str | None = None


class TaskPage(BaseModel):
    items: list[Task]
    page: int
    page_size: int
    total: int | None = None


class TaskResolutionRequest(BaseModel):
    resolution_type: Literal["Approved", "Rejected"]
    comment: str = Field(min_length=1, max_length=2_000)


class AccessRequestDetail(Task):
    table_name: str | None = None
    table_fully_qualified_name: str | None = None
    database: str | None = None
    schema_name: str | None = None
    access_type: str | None = None
    access_level: str | None = None
    columns: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    resolution_type: str | None = None
    resolution_comment: str | None = None


class QueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10_000)
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class CatalogColumn(BaseModel):
    id: str
    name: str
    data_type: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class CatalogOwner(BaseModel):
    id: str
    type: Literal["user", "team"]
    name: str | None = None
    display_name: str | None = None
    fully_qualified_name: str | None = None


class CatalogTable(BaseModel):
    id: str
    name: str
    fully_qualified_name: str | None = None
    description: str | None = None
    service: str | None = None
    database: str | None = None
    schema_name: str | None = None
    owners: list[CatalogOwner] = Field(default_factory=list)
    columns: list[CatalogColumn] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CatalogPage(BaseModel):
    items: list[CatalogTable]
    after: str | None = None


class AccessRequestCreate(BaseModel):
    table_id: str = Field(min_length=1, max_length=128)
    column_ids: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=100)
    access: Literal["READ", "WRITE"] = "READ"
    reason: str = Field(min_length=3, max_length=2_000)


class AccessRequestCreated(BaseModel):
    id: str
    request_id: str
    status: str | None = None
    assignee_count: int


class GrantedAccess(BaseModel):
    id: str
    request_id: str | None = None
    table_id: str | None = None
    table_name: str | None = None
    table_fully_qualified_name: str | None = None
    access_type: str | None = None
    access_level: str | None = None
    columns: list[str] = Field(default_factory=list)
    granted_at: datetime | None = None
    expires_at: datetime | None = None


class GrantedAccessPage(BaseModel):
    items: list[GrantedAccess]
    total: int

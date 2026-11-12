from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import CamelModel


class AdminDbColumnOut(CamelModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    default: str | None = None


class AdminDbTableOut(CamelModel):
    # `schema` là alias để tránh trùng thuộc tính `schema` của BaseModel.
    schema_name: str = Field(default="public", alias="schema")
    name: str
    kind: str
    row_estimate: int | None = None
    columns: list[AdminDbColumnOut]


class AdminDbSchemaOut(CamelModel):
    tables: list[AdminDbTableOut]
    generated_at: datetime


class AdminDbQueryIn(CamelModel):
    sql: str = Field(min_length=1, max_length=20000)
    max_rows: int = Field(default=100, ge=1, le=500)


class AdminDbResultColumnOut(CamelModel):
    name: str
    type: str


class AdminDbQueryOut(CamelModel):
    columns: list[AdminDbResultColumnOut]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int
    limit: int


AdminDbFilterOperator = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "starts_with",
    "ends_with",
    "is_null",
    "is_not_null",
]


class AdminDbFilterIn(CamelModel):
    column: str = Field(min_length=1, max_length=100)
    operator: AdminDbFilterOperator
    value: str | None = Field(default=None, max_length=2000)


class AdminDbTableRowsIn(CamelModel):
    # `schema` là alias để tránh trùng thuộc tính `schema` của BaseModel.
    schema_name: str = Field(default="public", alias="schema", max_length=100)
    columns: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = Field(default=None, max_length=100)
    order_dir: Literal["asc", "desc"] = "asc"
    filters: list[AdminDbFilterIn] = Field(default_factory=list, max_length=10)


class AdminDbTableRowsOut(CamelModel):
    columns: list[AdminDbResultColumnOut]
    rows: list[list[Any]]
    row_count: int
    limit: int
    offset: int
    has_more: bool
    duration_ms: int

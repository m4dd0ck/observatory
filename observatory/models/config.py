"""Configuration models for the Data Quality Observatory."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    """Data source configuration."""

    type: Literal["csv", "parquet", "duckdb", "sqlite"]
    path: Path | None = None
    connection_string: str | None = None
    table: str | None = None
    query: str | None = None  # custom sql if you need it


class ColumnSchema(BaseModel):
    """Schema definition for a single column."""

    name: str
    dtype: str
    nullable: bool = True


class CheckConfig(BaseModel):
    """Individual check configuration."""

    name: str
    type: str  # e.g. 'null_check', 'range_check', etc
    severity: Literal["info", "warning", "critical"] = "warning"
    enabled: bool = True

    column: str | None = None
    columns: list[str] | list[ColumnSchema] | None = None
    condition: str | None = None
    threshold: float | None = None  # e.g. max null percentage
    min: float | None = None
    max: float | None = None
    pattern: str | None = None  # regex for string validation
    query: str | None = None  # custom sql check
    allowed_values: list[Any] | None = None  # for enum-style validation
    max_age_hours: int | None = None  # freshness check
    timestamp_column: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert check config to dictionary for executor."""
        return self.model_dump(exclude_none=True)


class CheckSuiteConfig(BaseModel):
    """Complete check suite configuration."""

    name: str
    description: str = ""
    source: SourceConfig
    checks: list[CheckConfig]
    tags: list[str] = Field(default_factory=list)
    owner: str | None = None


class ObservatorySettings(BaseModel):
    """Global observatory settings."""

    results_database: Path = Path("observatory.db")
    log_level: str = "INFO"
    sample_failure_limit: int = 5
    retention_days: int = 90

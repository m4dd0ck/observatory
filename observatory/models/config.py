"""Configuration models for the Data Quality Observatory."""

from pathlib import Path
from typing import Literal, Any

from pydantic import BaseModel, Field


# took a lot of inspiration from great expectations' datasource config here
# they've figured out a nice pattern for supporting multiple backends
class SourceConfig(BaseModel):
    """Data source configuration."""

    # not sure if we need all these options but better to have them
    # TODO: maybe add support for remote sources like s3/gcs?
    type: Literal["csv", "parquet", "duckdb", "sqlite"]
    path: Path | None = None
    connection_string: str | None = None
    table: str | None = None
    query: str | None = None  # custom sql if you need it


class ColumnSchema(BaseModel):
    """Schema definition for a single column."""

    # keeping this simple for now, might need to expand later
    name: str
    dtype: str  # TODO: should probably validate this is a real dtype
    nullable: bool = True


class CheckConfig(BaseModel):
    """Individual check configuration."""

    name: str
    type: str  # e.g. 'null_check', 'range_check', etc
    severity: Literal["info", "warning", "critical"] = "warning"
    enabled: bool = True  # handy for temporarily disabling checks without deleting

    # type-specific fields - this got a bit messy tbh
    # great expectations handles this more elegantly with their expectation classes
    # but this works for now and is easier to serialize to yaml
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
        # exclude_none keeps the output clean
        return self.model_dump(exclude_none=True)


class CheckSuiteConfig(BaseModel):
    """Complete check suite configuration."""

    # similar to great expectations' checkpoint concept
    # groups related checks together
    name: str
    description: str = ""
    source: SourceConfig
    checks: list[CheckConfig]
    tags: list[str] = Field(default_factory=list)  # for filtering/grouping
    owner: str | None = None  # good for alerting


class ObservatorySettings(BaseModel):
    """Global observatory settings."""

    # defaults that work for most cases
    results_database: Path = Path("observatory.db")
    log_level: str = "INFO"
    parallel_checks: bool = False  # TODO: implement this, would be nice for large suites
    sample_failure_limit: int = 5  # don't dump too many failure examples
    retention_days: int = 90  # how long to keep historical results

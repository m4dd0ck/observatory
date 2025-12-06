"""Pydantic models for configuration and results."""

# inspired by how great expectations organizes their expectations and validation results
# keeping configs separate from results felt cleaner

from observatory.models.config import (
    CheckConfig,
    CheckSuiteConfig,
    ObservatorySettings,
    SourceConfig,
)
from observatory.models.results import CheckResult, RunResult

__all__ = [
    "SourceConfig",
    "CheckConfig",
    "CheckSuiteConfig",
    "ObservatorySettings",
    "CheckResult",
    "RunResult",
]

"""Data Quality Observatory - A production-grade data quality framework."""

from observatory.main import Observatory
from observatory.models.results import CheckResult, RunResult
from observatory.models.config import CheckSuiteConfig, SourceConfig, CheckConfig

__version__ = "0.1.0"
__all__ = [
    "Observatory",
    "CheckResult",
    "RunResult",
    "CheckSuiteConfig",
    "SourceConfig",
    "CheckConfig",
]

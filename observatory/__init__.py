"""Data quality checks for tables and files."""

from observatory.main import Observatory
from observatory.models.config import CheckConfig, CheckSuiteConfig, SourceConfig
from observatory.models.results import CheckResult, RunResult

__version__ = "0.1.1"
__all__ = [
    "Observatory",
    "CheckResult",
    "RunResult",
    "CheckSuiteConfig",
    "SourceConfig",
    "CheckConfig",
]

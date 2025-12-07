"""Base class for all check types."""

from abc import ABC, abstractmethod
from typing import Any

import duckdb

from observatory.models.results import CheckResult


class BaseCheck(ABC):
    """Abstract base class for all check types."""

    check_type: str

    @abstractmethod
    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute the check and return result.

        Args:
            conn: DuckDB connection to use for queries.
            table: Table name or path to check.
            config: Check-specific configuration.

        Returns:
            CheckResult with status, metrics, and details.
        """
        pass

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate check configuration, raise ValueError if invalid.

        Args:
            config: Check configuration to validate.

        Raises:
            ValueError: If configuration is invalid.
        """
        pass

"""Base class for all check types."""

from abc import ABC, abstractmethod
from typing import Any

import duckdb

from observatory.models.results import CheckResult


class BaseCheck(ABC):
    """Abstract base class for all check types.

    every check type
    inherits from this and implements execute() and validate_config().
    keeps things nice and consistent.
    """

    # subclasses gotta set this - it's how the registry finds you
    check_type: str  # e.g., "schema", "validity", "completeness"

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
        # all the actual logic lives in subclasses
        pass

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate check configuration, raise ValueError if invalid.

        call this before execute() or you'll get weird errors later.
        trust me, it's worth the extra validation step.

        Args:
            config: Check configuration to validate.

        Raises:
            ValueError: If configuration is invalid.
        """
        pass

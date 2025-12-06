"""Main Observatory class - the entry point for running data quality checks."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from observatory.checks.registry import get_default_registry
from observatory.connectors.duckdb_connector import DuckDBConnector
from observatory.models.config import CheckSuiteConfig, ObservatorySettings
from observatory.models.results import CheckResult, RunResult
from observatory.storage.duckdb_store import DuckDBStore


class Observatory:
    """Main class for running data quality checks."""

    def __init__(
        self,
        settings: ObservatorySettings | None = None,
        results_db: Path | None = None,
    ) -> None:
        """Initialize the Observatory.

        Args:
            settings: Observatory settings. If not provided, uses defaults.
            results_db: Path to results database. Overrides settings if provided.
        """
        self.settings = settings or ObservatorySettings()
        if results_db:
            self.settings.results_database = results_db

        self._registry = get_default_registry()
        self._store = DuckDBStore(self.settings.results_database)
        self._connector = DuckDBConnector()

    def run_suite(self, config_path: str | Path) -> RunResult:
        """Run a check suite from a YAML configuration file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            RunResult with all check results.
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            raw_config = yaml.safe_load(f)

        suite_config = CheckSuiteConfig(**raw_config)
        return self.run(suite_config)

    def run(self, suite: CheckSuiteConfig) -> RunResult:
        """Run a check suite.

        Args:
            suite: Check suite configuration.

        Returns:
            RunResult with all check results.
        """
        started_at = datetime.now(UTC)
        check_results: list[CheckResult] = []

        # Connect to data source
        conn = self._connector.connect(suite.source)
        table_name = self._connector.get_table_name(suite.source)

        # Execute each check
        for check_config in suite.checks:
            if not check_config.enabled:
                continue

            try:
                check_class = self._registry.get(check_config.type)
                check_instance = check_class()

                config_dict = check_config.to_dict()
                result = check_instance.execute(conn, table_name, config_dict)
                check_results.append(result)

            except Exception as e:
                # Record error for this check
                check_results.append(
                    CheckResult(
                        check_name=check_config.name,
                        check_type=check_config.type,
                        status="error",
                        severity=check_config.severity,
                        message=f"Check execution failed: {e}",
                    )
                )

        completed_at = datetime.now(UTC)
        duration = (completed_at - started_at).total_seconds()

        run_result = RunResult(
            suite_name=suite.name,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            check_results=check_results,
            metadata={
                "source_type": suite.source.type,
                "source_path": str(suite.source.path) if suite.source.path else None,
                "tags": suite.tags,
                "owner": suite.owner,
            },
        )

        # Persist results
        self._store.save_run(run_result)

        return run_result

    def get_run_history(
        self, suite_name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get historical run results.

        Args:
            suite_name: Filter by suite name. If None, returns all.
            limit: Maximum number of runs to return.

        Returns:
            List of run summaries.
        """
        return self._store.get_runs(suite_name=suite_name, limit=limit)

    def get_check_trends(
        self, suite_name: str, check_name: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get trend data for a specific check.

        Args:
            suite_name: Name of the suite.
            check_name: Name of the check.
            days: Number of days to look back.

        Returns:
            List of check results over time.
        """
        return self._store.get_check_trends(suite_name, check_name, days)

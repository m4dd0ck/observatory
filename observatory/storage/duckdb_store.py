"""DuckDB storage for check results."""

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import duckdb

from observatory.models.results import RunResult


def json_serializer(obj: Any) -> str | float:
    """JSON serializer for the value types DuckDB hands back that json cannot encode.

    Sample failures carry raw column values, so dates, times, decimals, UUIDs and bytes all
    show up here, not only datetimes.
    """
    if isinstance(obj, datetime | date | time):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class DuckDBStore:
    """Stores check results and metrics in DuckDB."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the store.

        Args:
            db_path: Path to the DuckDB database file.
        """
        self.db_path = db_path
        self._ensure_schema()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a database connection."""
        return duckdb.connect(str(self.db_path))

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_connection()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_runs (
                run_id VARCHAR PRIMARY KEY,
                suite_name VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                duration_seconds DOUBLE,
                total_checks INTEGER,
                passed_checks INTEGER,
                warning_checks INTEGER,
                failed_checks INTEGER,
                error_checks INTEGER,
                overall_status VARCHAR,
                metadata JSON
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_results (
                result_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                check_name VARCHAR NOT NULL,
                check_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                severity VARCHAR NOT NULL,
                metric_value DOUBLE,
                threshold DOUBLE,
                message TEXT,
                details JSON,
                sample_failures JSON,
                execution_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_metrics (
                metric_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                suite_name VARCHAR NOT NULL,
                check_name VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                metric_value DOUBLE NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_suite_time
            ON check_runs(suite_name, started_at)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_run
            ON check_results(run_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_suite_time
            ON quality_metrics(suite_name, recorded_at)
        """)

        conn.close()

    def save_run(self, run_result: RunResult) -> None:
        """Save a run result to the database.

        Args:
            run_result: The run result to save.
        """
        conn = self._get_connection()

        summary = run_result.summary

        conn.execute(
            """
            INSERT INTO check_runs (
                run_id, suite_name, started_at, completed_at, duration_seconds,
                total_checks, passed_checks, warning_checks, failed_checks,
                error_checks, overall_status, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(run_result.run_id),
                run_result.suite_name,
                run_result.started_at,
                run_result.completed_at,
                run_result.duration_seconds,
                summary["total"],
                summary["passed"],
                summary["warning"],
                summary["failed"],
                summary["error"],
                run_result.overall_status,
                json.dumps(run_result.metadata),
            ],
        )

        for check_result in run_result.check_results:
            result_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO check_results (
                    result_id, run_id, check_name, check_type, status, severity,
                    metric_value, threshold, message, details, sample_failures,
                    execution_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    result_id,
                    str(run_result.run_id),
                    check_result.check_name,
                    check_result.check_type,
                    check_result.status,
                    check_result.severity,
                    check_result.metric_value,
                    check_result.threshold,
                    check_result.message,
                    json.dumps(check_result.details, default=json_serializer),
                    json.dumps(check_result.sample_failures, default=json_serializer),
                    check_result.execution_time_ms,
                ],
            )

            if check_result.metric_value is not None:
                metric_id = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO quality_metrics (
                        metric_id, run_id, suite_name, check_name,
                        metric_name, metric_value
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        metric_id,
                        str(run_result.run_id),
                        run_result.suite_name,
                        check_result.check_name,
                        "check_metric",
                        check_result.metric_value,
                    ],
                )

        conn.close()

    def get_runs(self, suite_name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Get historical run results.

        Args:
            suite_name: Filter by suite name.
            limit: Maximum runs to return.

        Returns:
            List of run summaries.
        """
        conn = self._get_connection()

        if suite_name:
            query = """
                SELECT * FROM check_runs
                WHERE suite_name = ?
                ORDER BY started_at DESC
                LIMIT ?
            """
            result = conn.execute(query, [suite_name, limit]).fetchall()
        else:
            query = """
                SELECT * FROM check_runs
                ORDER BY started_at DESC
                LIMIT ?
            """
            result = conn.execute(query, [limit]).fetchall()

        columns = [desc[0] for desc in conn.description]
        conn.close()

        return [dict(zip(columns, row)) for row in result]

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
        conn = self._get_connection()

        cutoff = datetime.now(UTC) - timedelta(days=days)

        query = """
            SELECT
                cr.check_name,
                cr.status,
                cr.metric_value,
                cr.threshold,
                r.started_at
            FROM check_results cr
            JOIN check_runs r ON cr.run_id = r.run_id
            WHERE r.suite_name = ?
              AND cr.check_name = ?
              AND r.started_at > ?
            ORDER BY r.started_at
        """

        result = conn.execute(query, [suite_name, check_name, cutoff]).fetchall()
        columns = [desc[0] for desc in conn.description]
        conn.close()

        return [dict(zip(columns, row)) for row in result]

    def get_latest_results(self, suite_name: str) -> list[dict[str, Any]]:
        """Get results from the latest run for a suite.

        Args:
            suite_name: Name of the suite.

        Returns:
            List of check results from the latest run.
        """
        conn = self._get_connection()

        query = """
            WITH latest_run AS (
                SELECT run_id
                FROM check_runs
                WHERE suite_name = ?
                ORDER BY started_at DESC
                LIMIT 1
            )
            SELECT cr.*
            FROM check_results cr
            JOIN latest_run lr ON cr.run_id = lr.run_id
        """

        result = conn.execute(query, [suite_name]).fetchall()
        columns = [desc[0] for desc in conn.description]
        conn.close()

        return [dict(zip(columns, row)) for row in result]

    def cleanup_old_runs(self, retention_days: int = 90) -> int:
        """Delete runs older than retention period.

        Args:
            retention_days: Number of days to retain.

        Returns:
            Number of runs deleted.
        """
        conn = self._get_connection()

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        old_runs = conn.execute(
            "SELECT run_id FROM check_runs WHERE started_at < ?", [cutoff]
        ).fetchall()

        if not old_runs:
            conn.close()
            return 0

        run_ids = [r[0] for r in old_runs]
        placeholders = ", ".join("?" * len(run_ids))

        conn.execute(f"DELETE FROM check_results WHERE run_id IN ({placeholders})", run_ids)
        conn.execute(f"DELETE FROM quality_metrics WHERE run_id IN ({placeholders})", run_ids)
        conn.execute(f"DELETE FROM check_runs WHERE run_id IN ({placeholders})", run_ids)

        conn.close()
        return len(run_ids)

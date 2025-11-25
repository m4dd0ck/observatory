"""Uniqueness checks for duplicate detection."""

import time
from typing import Any

import duckdb

from observatory.checks.base import BaseCheck
from observatory.models.results import CheckResult


class UniquenessCheck(BaseCheck):
    """Checks for duplicate values in columns.

    duplicates are sneaky - they can mess up joins, aggregations, everything.
    this check catches them early. supports both single column and composite
    uniqueness (like standard data quality checks).
    """

    check_type = "uniqueness"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate uniqueness check configuration."""
        # support both 'column' (single) and 'columns' (composite)
        if "column" not in config and "columns" not in config:
            raise ValueError("UniquenessCheck requires 'column' or 'columns' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute uniqueness validation check."""
        start_time = time.time()
        self.validate_config(config)

        # support single column or composite uniqueness
        # nice to have both options
        if "columns" in config:
            columns = config["columns"]
            column_expr = ", ".join(columns)
            column_display = f"({column_expr})"
        else:
            columns = [config["column"]]
            column_expr = config["column"]
            column_display = config["column"]

        severity = config.get("severity", "warning")
        check_name = config.get("name", f"uniqueness_{column_display}")
        threshold = config.get("threshold", 0.0)  # max allowed duplicate rate

        try:
            # count total rows and distinct values in one query
            # the WHERE clause filters out nulls - they don't count as duplicates
            query = f"""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT ({column_expr})) as distinct_count
                FROM {table}
                WHERE {columns[0]} IS NOT NULL
            """
            result = conn.execute(query).fetchone()
            if result is None:
                total_rows, distinct_count = 0, 0
            else:
                total_rows, distinct_count = result

            if total_rows == 0:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="warning",
                    severity=severity,
                    metric_value=0,
                    message=f"Table is empty or all values are null for '{column_display}'",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # duplicates = total rows - distinct values
            # simple math but easy to mess up if you're not careful
            duplicates = total_rows - distinct_count
            duplicate_rate = duplicates / total_rows if total_rows > 0 else 0

            # get sample duplicates - show which values are duplicated and how many times
            # the ORDER BY dup_count DESC is key - show the worst offenders first
            sample_failures = []
            if duplicates > 0:
                sample_query = f"""
                    WITH duplicates AS (
                        SELECT {column_expr}, COUNT(*) as dup_count
                        FROM {table}
                        WHERE {columns[0]} IS NOT NULL
                        GROUP BY {column_expr}
                        HAVING COUNT(*) > 1
                    )
                    SELECT * FROM duplicates
                    ORDER BY dup_count DESC
                    LIMIT 5
                """
                samples = conn.execute(sample_query).fetchall()
                col_names = [desc[0] for desc in conn.description]
                sample_failures = [dict(zip(col_names, row)) for row in samples]

            execution_time_ms = int((time.time() - start_time) * 1000)

            passed = duplicate_rate <= threshold

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed" if passed else "failed",
                severity=severity,
                metric_value=duplicates,
                threshold=int(threshold * total_rows) if total_rows > 0 else 0,
                message=f"Found {duplicates:,} duplicate rows ({duplicate_rate:.2%}) for '{column_display}'",
                details={
                    "column": column_display,
                    "columns": columns,
                    "total_rows": total_rows,
                    "distinct_count": distinct_count,
                    "duplicate_count": duplicates,
                    "duplicate_rate": duplicate_rate,
                    "threshold": threshold,
                },
                sample_failures=sample_failures,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="error",
                severity=severity,
                message=f"Failed to execute uniqueness check: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

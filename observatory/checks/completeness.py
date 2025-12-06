"""Completeness checks for null rates and missing values."""

import time
from typing import Any

import duckdb

from observatory.checks.base import BaseCheck
from observatory.models.results import CheckResult


class CompletenessCheck(BaseCheck):
    """Checks for null rates and missing value patterns.

    this is probably the most commonly used check - null values creep in
    everywhere and this catches them early. pretty standard pattern
    but we added threshold support so you can allow some nulls if needed.
    """

    check_type = "completeness"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate completeness check configuration."""
        if "column" not in config:
            raise ValueError("CompletenessCheck requires 'column' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute completeness check."""
        start_time = time.time()
        self.validate_config(config)

        column = config["column"]
        severity = config.get("severity", "warning")
        check_name = config.get("name", f"completeness_{column}")
        threshold = config.get("threshold", 0.0)  # max allowed null rate

        try:
            # single query to get all the stats we need - duckdb is fast but
            # no reason to make multiple round trips
            query = f"""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT({column}) as non_null_count,
                    COUNT(*) - COUNT({column}) as null_count
                FROM {table}
            """
            result = conn.execute(query).fetchone()
            if result is None:
                total_rows, non_null_count, null_count = 0, 0, 0
            else:
                total_rows, non_null_count, null_count = result

            # edge case: empty table
            if total_rows == 0:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="warning",
                    severity=severity,
                    metric_value=0,
                    message=f"Table is empty, cannot check completeness of '{column}'",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            null_rate = null_count / total_rows

            # grab some sample nulls for debugging - super helpfull when you're
            # trying to figure out why data is missing
            sample_failures = []
            if null_count > 0:
                sample_query = f"""
                    SELECT * FROM {table}
                    WHERE {column} IS NULL
                    LIMIT 5
                """
                samples = conn.execute(sample_query).fetchall()
                columns = [desc[0] for desc in conn.description]
                sample_failures = [dict(zip(columns, row)) for row in samples]

            execution_time_ms = int((time.time() - start_time) * 1000)

            # check against threshold - learned the hard way that sometimes
            # you need to tolerate some nulls (looking at you, optional fields)
            if null_rate > threshold:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="failed",
                    severity=severity,
                    metric_value=null_count,
                    threshold=int(threshold * total_rows),
                    message=(
                        f"Column '{column}' has {null_count:,} null values "
                        f"({null_rate:.2%}), exceeds threshold of {threshold:.2%}"
                    ),
                    details={
                        "column": column,
                        "total_rows": total_rows,
                        "null_count": null_count,
                        "non_null_count": non_null_count,
                        "null_rate": null_rate,
                        "threshold": threshold,
                    },
                    sample_failures=sample_failures,
                    execution_time_ms=execution_time_ms,
                )

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed",
                severity=severity,
                metric_value=null_count,
                threshold=int(threshold * total_rows),
                message=f"Column '{column}' completeness check passed. Null rate: {null_rate:.2%}",
                details={
                    "column": column,
                    "total_rows": total_rows,
                    "null_count": null_count,
                    "non_null_count": non_null_count,
                    "null_rate": null_rate,
                    "threshold": threshold,
                },
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            # don't let one bad check bring down the whole run
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="error",
                severity=severity,
                message=f"Failed to check completeness: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

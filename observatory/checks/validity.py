"""Validity checks for range validation, allowed values, and custom SQL."""

import time
from typing import Any

import duckdb

from observatory.checks.base import BaseCheck
from observatory.models.results import CheckResult


class RangeCheck(BaseCheck):
    """Validates values fall within an expected range."""

    check_type = "range"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate range check configuration."""
        if "column" not in config:
            raise ValueError("RangeCheck requires 'column' configuration")
        if "min" not in config and "max" not in config:
            raise ValueError("RangeCheck requires 'min' and/or 'max' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute range validation check."""
        start_time = time.time()
        self.validate_config(config)

        column = config["column"]
        min_val = config.get("min")
        max_val = config.get("max")
        severity = config.get("severity", "warning")
        check_name = config.get("name", f"range_{column}")
        threshold = config.get("threshold", 0.0)  # max allowed failure rate

        conditions = []
        if min_val is not None:
            conditions.append(f"{column} < {min_val}")
        if max_val is not None:
            conditions.append(f"{column} > {max_val}")

        where_clause = " OR ".join(conditions)

        try:
            query = f"""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (WHERE {where_clause}) as failures,
                    COUNT(*) FILTER (WHERE {column} IS NULL) as nulls
                FROM {table}
            """
            result = conn.execute(query).fetchone()
            if result is None:
                total_rows, failures, nulls = 0, 0, 0
            else:
                total_rows, failures, nulls = result

            if total_rows == 0:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="warning",
                    severity=severity,
                    metric_value=0,
                    message=f"Table is empty, cannot check range for '{column}'",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            non_null_rows = total_rows - nulls
            failure_rate = failures / non_null_rows if non_null_rows > 0 else 0

            sample_failures = []
            if failures > 0:
                sample_query = f"""
                    SELECT * FROM {table}
                    WHERE {where_clause}
                    LIMIT 5
                """
                samples = conn.execute(sample_query).fetchall()
                columns = [desc[0] for desc in conn.description]
                sample_failures = [dict(zip(columns, row)) for row in samples]

            execution_time_ms = int((time.time() - start_time) * 1000)

            passed = failure_rate <= threshold

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed" if passed else "failed",
                severity=severity,
                metric_value=failures,
                threshold=int(threshold * non_null_rows) if non_null_rows > 0 else 0,
                message=(
                    f"Found {failures:,} rows ({failure_rate:.2%}) "
                    f"outside range [{min_val}, {max_val}]"
                ),
                details={
                    "column": column,
                    "min": min_val,
                    "max": max_val,
                    "total_rows": total_rows,
                    "null_count": nulls,
                    "failure_count": failures,
                    "failure_rate": failure_rate,
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
                message=f"Failed to execute range check: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class AllowedValuesCheck(BaseCheck):
    """Validates values are within an allowed set."""

    check_type = "allowed_values"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate allowed values check configuration."""
        if "column" not in config:
            raise ValueError("AllowedValuesCheck requires 'column' configuration")
        if "allowed_values" not in config:
            raise ValueError("AllowedValuesCheck requires 'allowed_values' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute allowed values validation check."""
        start_time = time.time()
        self.validate_config(config)

        column = config["column"]
        allowed_values = config["allowed_values"]
        severity = config.get("severity", "warning")
        check_name = config.get("name", f"allowed_values_{column}")
        threshold = config.get("threshold", 0.0)

        if all(isinstance(v, (int, float)) for v in allowed_values):
            values_str = ", ".join(str(v) for v in allowed_values)
        else:
            values_str = ", ".join(f"'{v}'" for v in allowed_values)

        try:
            query = f"""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (
                        WHERE {column} NOT IN ({values_str}) AND {column} IS NOT NULL
                    ) as failures,
                    COUNT(*) FILTER (WHERE {column} IS NULL) as nulls
                FROM {table}
            """
            result = conn.execute(query).fetchone()
            if result is None:
                total_rows, failures, nulls = 0, 0, 0
            else:
                total_rows, failures, nulls = result

            if total_rows == 0:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="warning",
                    severity=severity,
                    metric_value=0,
                    message=f"Table is empty, cannot check allowed values for '{column}'",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            non_null_rows = total_rows - nulls
            failure_rate = failures / non_null_rows if non_null_rows > 0 else 0

            sample_failures = []
            if failures > 0:
                sample_query = f"""
                    SELECT DISTINCT {column} as invalid_value, COUNT(*) as count
                    FROM {table}
                    WHERE {column} NOT IN ({values_str}) AND {column} IS NOT NULL
                    GROUP BY {column}
                    LIMIT 5
                """
                samples = conn.execute(sample_query).fetchall()
                sample_failures = [
                    {"invalid_value": row[0], "count": row[1]} for row in samples
                ]

            execution_time_ms = int((time.time() - start_time) * 1000)

            passed = failure_rate <= threshold

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed" if passed else "failed",
                severity=severity,
                metric_value=failures,
                threshold=int(threshold * non_null_rows) if non_null_rows > 0 else 0,
                message=(
                    f"Found {failures:,} rows ({failure_rate:.2%}) "
                    "with values not in allowed set"
                ),
                details={
                    "column": column,
                    "allowed_values": allowed_values,
                    "total_rows": total_rows,
                    "null_count": nulls,
                    "failure_count": failures,
                    "failure_rate": failure_rate,
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
                message=f"Failed to execute allowed values check: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class CustomSQLCheck(BaseCheck):
    """Executes a custom SQL query for validation.

    Query should return failure count as first column. Use {table} as placeholder.
    """

    check_type = "custom_sql"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate custom SQL check configuration."""
        if "query" not in config:
            raise ValueError("CustomSQLCheck requires 'query' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute custom SQL validation check."""
        start_time = time.time()
        self.validate_config(config)

        query = config["query"]
        severity = config.get("severity", "warning")
        check_name = config.get("name", "custom_sql_check")
        threshold = config.get("threshold", 0)

        query = query.replace("{table}", table)

        try:
            result = conn.execute(query).fetchone()

            if result is None:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="error",
                    severity=severity,
                    message="Custom SQL query returned no results",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            failures = result[0] if isinstance(result[0], (int, float)) else 0

            execution_time_ms = int((time.time() - start_time) * 1000)

            if threshold < 1:
                # get total count for rate comparison
                total_query = f"SELECT COUNT(*) FROM {table}"
                total_result = conn.execute(total_query).fetchone()
                total_rows = total_result[0] if total_result else 0
                failure_rate = failures / total_rows if total_rows > 0 else 0
                passed = failure_rate <= threshold
                message = f"Custom SQL check found {failures:,} failures ({failure_rate:.2%})"
            else:
                passed = failures <= threshold
                message = f"Custom SQL check found {failures:,} failures (threshold: {threshold})"

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed" if passed else "failed",
                severity=severity,
                metric_value=failures,
                threshold=threshold,
                message=message,
                details={
                    "query": query,
                    "failures": failures,
                    "threshold": threshold,
                },
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="error",
                severity=severity,
                message=f"Failed to execute custom SQL check: {e}",
                details={"query": query},
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

"""Freshness checks for data staleness detection."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import duckdb

from observatory.checks.base import BaseCheck
from observatory.models.results import CheckResult


class FreshnessCheck(BaseCheck):
    """Checks for data freshness based on timestamp columns.

    stale data is often wrong data. this check makes sure your data pipelines
    are actually running. set max_age_hours based on how often your data
    should update - daily loads get 36 hours (buffer for weekends), hourly
    gets maybe 3-4 hours.

    learned the hard way that timezone handling is tricky here. we assume
    UTC if no timezone is specified.
    """

    check_type = "freshness"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate freshness check configuration."""
        # support both 'column' and 'timestamp_column' for backwards compat
        if "column" not in config and "timestamp_column" not in config:
            raise ValueError("FreshnessCheck requires 'column' or 'timestamp_column' configuration")
        if "max_age_hours" not in config:
            raise ValueError("FreshnessCheck requires 'max_age_hours' configuration")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute freshness validation check."""
        start_time = time.time()
        self.validate_config(config)

        # support both config key names - some tools use timestamp_column
        column = config.get("column") or config.get("timestamp_column")
        max_age_hours = config["max_age_hours"]
        severity = config.get("severity", "warning")
        check_name = config.get("name", f"freshness_{column}")

        try:
            # get the most recent timestamp - that's what we care about
            query = f"""
                SELECT
                    MAX({column}) as max_timestamp,
                    MIN({column}) as min_timestamp,
                    COUNT(*) as total_rows
                FROM {table}
                WHERE {column} IS NOT NULL
            """
            result = conn.execute(query).fetchone()
            if result is None:
                max_timestamp, min_timestamp, total_rows = None, None, 0
            else:
                max_timestamp, min_timestamp, total_rows = result

            if total_rows == 0 or max_timestamp is None:
                return CheckResult(
                    check_name=check_name,
                    check_type=self.check_type,
                    status="warning",
                    severity=severity,
                    metric_value=None,
                    message=f"No non-null values in '{column}' to check freshness",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # calculate age - now minus most recent timestamp
            now = datetime.now(timezone.utc)

            # handle different timestamp formats - duckdb can return strings
            # or datetime objects depending on the column type
            # TODO: this is kinda brittle, might need to handle more formats
            # note to self: look into dateutil.parser
            if isinstance(max_timestamp, str):
                # try parsing ISO format first
                ts_str = max_timestamp
                try:
                    max_timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    # fallback to common format
                    max_timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

            # make timestamp timezone-aware if needed - assume UTC
            # this has bitten me before when comparing tz-aware and naive datetimes
            if max_timestamp.tzinfo is None:
                max_timestamp = max_timestamp.replace(tzinfo=timezone.utc)

            age = now - max_timestamp
            age_hours = age.total_seconds() / 3600

            execution_time_ms = int((time.time() - start_time) * 1000)

            passed = age_hours <= max_age_hours

            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="passed" if passed else "failed",
                severity=severity,
                metric_value=round(age_hours, 2),
                threshold=max_age_hours,
                message=f"Data is {age_hours:.1f} hours old (max: {max_age_hours} hours)",
                details={
                    "column": column,
                    "max_timestamp": str(max_timestamp),
                    "min_timestamp": str(min_timestamp),
                    "age_hours": round(age_hours, 2),
                    "max_age_hours": max_age_hours,
                    "total_rows": total_rows,
                },
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="error",
                severity=severity,
                message=f"Failed to execute freshness check: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

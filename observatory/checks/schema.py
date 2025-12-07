"""Schema validation checks."""

import time
from typing import Any

import duckdb

from observatory.checks.base import BaseCheck
from observatory.models.results import CheckResult


class SchemaCheck(BaseCheck):
    """Validates table schema: column presence, types, and nullability."""

    check_type = "schema"

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate schema check configuration."""
        if "columns" not in config:
            raise ValueError("SchemaCheck requires 'columns' configuration")
        if not isinstance(config["columns"], list):
            raise ValueError("'columns' must be a list")
        # each column can be a string (just name) or dict (name + type + nullable)
        for col in config["columns"]:
            if isinstance(col, dict) and "name" not in col:
                raise ValueError("Each column must have a 'name'")

    def execute(
        self, conn: duckdb.DuckDBPyConnection, table: str, config: dict[str, Any]
    ) -> CheckResult:
        """Execute schema validation check."""
        start_time = time.time()
        self.validate_config(config)

        expected_columns = config["columns"]
        severity = config.get("severity", "warning")
        check_name = config.get("name", "schema_check")

        try:
            # DESCRIBE needs SELECT * for function-based table refs
            if table.startswith("read_"):
                schema_query = f"DESCRIBE SELECT * FROM {table}"
            else:
                schema_query = f"DESCRIBE {table}"
            actual_schema = conn.execute(schema_query).fetchall()
        except Exception as e:
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="error",
                severity=severity,
                message=f"Failed to get schema: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        # build lookup of actual columns for easy checking
        actual_columns = {
            row[0]: {"dtype": row[1], "nullable": row[2] == "YES"}
            for row in actual_schema
        }

        issues = []
        sample_failures = []

        # check each expected column
        for expected in expected_columns:
            if isinstance(expected, str):
                # simple column name check - just verify it exists
                col_name = expected
                if col_name not in actual_columns:
                    issues.append(f"Missing column: {col_name}")
                    sample_failures.append({"issue": "missing_column", "column": col_name})
            else:
                # detailed column spec - check name, type, and nullability
                if isinstance(expected, dict):
                    col_name = expected.get("name", "")
                    expected_dtype = expected.get("dtype")
                    expected_nullable = expected.get("nullable", True)
                else:
                    col_name = expected.name
                    expected_dtype = getattr(expected, "dtype", None)
                    expected_nullable = getattr(expected, "nullable", True)

                if col_name not in actual_columns:
                    issues.append(f"Missing column: {col_name}")
                    sample_failures.append({"issue": "missing_column", "column": col_name})
                    continue

                actual = actual_columns[col_name]

                if expected_dtype:
                    actual_dtype = actual["dtype"].upper()
                    expected_dtype_upper = expected_dtype.upper()
                    type_matches = (
                        expected_dtype_upper in actual_dtype
                        or actual_dtype in expected_dtype_upper
                        or self._types_compatible(expected_dtype_upper, actual_dtype)
                    )
                    if not type_matches:
                        issues.append(
                            f"Column '{col_name}' type mismatch: "
                            f"expected {expected_dtype}, got {actual['dtype']}"
                        )
                        sample_failures.append({
                            "issue": "type_mismatch",
                            "column": col_name,
                            "expected": expected_dtype,
                            "actual": actual["dtype"],
                        })

                if not expected_nullable and actual["nullable"]:
                    issues.append(
                        f"Column '{col_name}' should not be nullable"
                    )
                    sample_failures.append({
                        "issue": "nullable_mismatch",
                        "column": col_name,
                        "expected_nullable": str(expected_nullable),
                        "actual_nullable": str(actual["nullable"]),
                    })

        execution_time_ms = int((time.time() - start_time) * 1000)

        if issues:
            return CheckResult(
                check_name=check_name,
                check_type=self.check_type,
                status="failed",
                severity=severity,
                metric_value=len(issues),
                message=(
                    f"Schema validation failed with {len(issues)} issue(s): "
                    f"{'; '.join(issues[:3])}"
                ),
                details={
                    "issues": issues,
                    "expected_columns": len(expected_columns),
                    "actual_columns": len(actual_columns),
                },
                sample_failures=sample_failures[:5],
                execution_time_ms=execution_time_ms,
            )

        return CheckResult(
            check_name=check_name,
            check_type=self.check_type,
            status="passed",
            severity=severity,
            metric_value=0,
            message=f"Schema validation passed. All {len(expected_columns)} columns match.",
            details={
                "expected_columns": len(expected_columns),
                "actual_columns": len(actual_columns),
            },
            execution_time_ms=execution_time_ms,
        )

    def _types_compatible(self, expected: str, actual: str) -> bool:
        """Check if types are compatible with common aliases."""
        type_groups = [
            {"INT", "INTEGER", "BIGINT", "INT64", "INT32", "SMALLINT", "TINYINT", "HUGEINT"},
            {"FLOAT", "DOUBLE", "REAL", "FLOAT64", "FLOAT32", "DECIMAL", "NUMERIC"},
            {"VARCHAR", "STRING", "TEXT", "CHAR"},
            {"TIMESTAMP", "DATETIME", "DATETIME64"},
            {"DATE"},
            {"BOOLEAN", "BOOL"},
        ]

        for group in type_groups:
            if expected in group and actual in group:
                return True

        return False

"""Tests for schema validation checks."""

import pytest

from observatory.checks.schema import SchemaCheck


class TestSchemaCheck:
    """Tests for SchemaCheck."""

    def test_passes_with_matching_schema(self, test_db):
        """Should pass when schema matches expected columns."""
        check = SchemaCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "schema_check",
                "columns": [
                    {"name": "id", "dtype": "INTEGER"},
                    {"name": "name", "dtype": "VARCHAR"},
                    {"name": "age", "dtype": "INTEGER"},
                ],
            },
        )

        assert result.status == "passed"

    def test_detects_missing_column(self, test_db):
        """Should fail when expected column is missing."""
        check = SchemaCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "schema_check",
                "columns": [
                    {"name": "id", "dtype": "INTEGER"},
                    {"name": "nonexistent_column", "dtype": "VARCHAR"},
                ],
            },
        )

        assert result.status == "failed"
        assert "missing" in result.message.lower()

    def test_detects_type_mismatch(self, test_db):
        """Should fail when column type doesn't match."""
        check = SchemaCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "schema_check",
                "columns": [
                    {"name": "id", "dtype": "VARCHAR"},  # Wrong type
                ],
            },
        )

        assert result.status == "failed"
        assert "mismatch" in result.message.lower()

    def test_simple_column_list(self, test_db):
        """Should support simple column name list."""
        check = SchemaCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "schema_check",
                "columns": ["id", "name", "age"],
            },
        )

        assert result.status == "passed"

    def test_compatible_types(self, test_db):
        """Should accept compatible type aliases."""
        check = SchemaCheck()
        # BIGINT and INT64 should be compatible
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "schema_check",
                "columns": [
                    {"name": "id", "dtype": "INT"},  # Compatible with INTEGER
                ],
            },
        )

        assert result.status == "passed"

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = SchemaCheck()

        with pytest.raises(ValueError, match="'columns'"):
            check.validate_config({})

        with pytest.raises(ValueError, match="'columns' must be a list"):
            check.validate_config({"columns": "not_a_list"})

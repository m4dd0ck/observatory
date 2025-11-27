"""Tests for freshness checks."""

import pytest
from datetime import datetime, timezone, timedelta

import duckdb

from observatory.checks.freshness import FreshnessCheck


@pytest.fixture
def recent_data_db():
    """Database with recent timestamps."""
    conn = duckdb.connect(":memory:")
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)
    old = now - timedelta(hours=48)

    conn.execute(f"""
        CREATE TABLE test_data AS
        SELECT * FROM (VALUES
            (1, TIMESTAMP '{recent.strftime("%Y-%m-%d %H:%M:%S")}'),
            (2, TIMESTAMP '{old.strftime("%Y-%m-%d %H:%M:%S")}')
        ) AS t(id, updated_at)
    """)
    return conn


@pytest.fixture
def stale_data_db():
    """Database with old timestamps."""
    conn = duckdb.connect(":memory:")
    old = datetime.now(timezone.utc) - timedelta(days=30)

    conn.execute(f"""
        CREATE TABLE test_data AS
        SELECT * FROM (VALUES
            (1, TIMESTAMP '{old.strftime("%Y-%m-%d %H:%M:%S")}'),
            (2, TIMESTAMP '{old.strftime("%Y-%m-%d %H:%M:%S")}')
        ) AS t(id, updated_at)
    """)
    return conn


class TestFreshnessCheck:
    """Tests for FreshnessCheck."""

    def test_passes_with_fresh_data(self, recent_data_db):
        """Should pass when data is fresh."""
        check = FreshnessCheck()
        result = check.execute(
            recent_data_db,
            "test_data",
            {"name": "data_freshness", "column": "updated_at", "max_age_hours": 24},
        )

        assert result.status == "passed"
        assert result.metric_value < 24  # Less than 24 hours old

    def test_fails_with_stale_data(self, stale_data_db):
        """Should fail when data is stale."""
        check = FreshnessCheck()
        result = check.execute(
            stale_data_db,
            "test_data",
            {"name": "data_freshness", "column": "updated_at", "max_age_hours": 24},
        )

        assert result.status == "failed"
        assert result.metric_value > 24  # More than 24 hours old

    def test_includes_age_details(self, recent_data_db):
        """Should include age details in result."""
        check = FreshnessCheck()
        result = check.execute(
            recent_data_db,
            "test_data",
            {"name": "data_freshness", "column": "updated_at", "max_age_hours": 24},
        )

        assert "age_hours" in result.details
        assert "max_timestamp" in result.details

    def test_handles_timestamp_column_alias(self, recent_data_db):
        """Should support timestamp_column as alias for column."""
        check = FreshnessCheck()
        result = check.execute(
            recent_data_db,
            "test_data",
            {"name": "data_freshness", "timestamp_column": "updated_at", "max_age_hours": 24},
        )

        assert result.status == "passed"

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = FreshnessCheck()

        with pytest.raises(ValueError, match="'column' or 'timestamp_column'"):
            check.validate_config({})

        with pytest.raises(ValueError, match="'max_age_hours'"):
            check.validate_config({"column": "updated_at"})

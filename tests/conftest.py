"""Shared test fixtures."""

import tempfile
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def test_db():
    """In-memory DuckDB with test data."""
    conn = duckdb.connect(":memory:")

    # Create test table with various data quality issues
    conn.execute("""
        CREATE TABLE test_data AS
        SELECT * FROM (VALUES
            (1, 'Alice', 25, 50000.0, 'A', TIMESTAMP '2024-01-15 10:00:00'),
            (2, 'Bob', 30, 60000.0, 'B', TIMESTAMP '2024-01-15 11:00:00'),
            (3, 'Charlie', -5, 70000.0, 'A', TIMESTAMP '2024-01-15 12:00:00'),
            (4, 'Diana', 28, -1000.0, 'C', TIMESTAMP '2024-01-15 13:00:00'),
            (5, NULL, 35, 55000.0, 'B', TIMESTAMP '2024-01-15 14:00:00'),
            (6, 'Eve', NULL, 80000.0, 'INVALID', TIMESTAMP '2024-01-15 15:00:00'),
            (7, 'Frank', 40, NULL, 'A', TIMESTAMP '2024-01-14 10:00:00'),
            (1, 'Alice', 25, 50000.0, 'A', TIMESTAMP '2024-01-15 10:00:00'),  -- Duplicate
            (8, 'Grace', 150, 90000.0, 'B', TIMESTAMP '2024-01-10 10:00:00')
        ) AS t(id, name, age, salary, category, created_at)
    """)

    return conn


@pytest.fixture
def empty_db():
    """In-memory DuckDB with empty table."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE empty_data (
            id INTEGER,
            name VARCHAR,
            value DOUBLE
        )
    """)
    return conn


@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_parquet(temp_dir):
    """Create a sample parquet file for testing."""
    import pandas as pd

    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "value": [10.0, -5.0, 30.0, None, 200.0],
        "category": ["A", "B", "A", "C", "INVALID"],
    })

    path = temp_dir / "test.parquet"
    df.to_parquet(path)
    return path


@pytest.fixture
def sample_config(temp_dir, sample_parquet):
    """Create a sample check configuration."""
    config_content = f"""
name: test_suite
description: Test suite for unit testing
source:
  type: parquet
  path: {sample_parquet}
checks:
  - name: positive_values
    type: range
    column: value
    min: 0
    severity: critical
  - name: valid_categories
    type: allowed_values
    column: category
    allowed_values: [A, B, C]
    severity: warning
"""
    path = temp_dir / "checks.yaml"
    path.write_text(config_content)
    return path

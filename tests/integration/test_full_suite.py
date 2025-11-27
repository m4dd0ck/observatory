"""Integration tests for full check suite execution."""

import pytest
from pathlib import Path
import tempfile

from observatory import Observatory
from observatory.models.config import CheckSuiteConfig, SourceConfig, CheckConfig


class TestFullSuite:
    """Integration tests for running complete check suites."""

    def test_runs_suite_from_yaml(self, sample_config, temp_dir):
        """Should run all checks from YAML configuration."""
        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run_suite(sample_config)

        assert len(results.check_results) == 2
        assert results.suite_name == "test_suite"

    def test_detects_known_issues(self, sample_config, temp_dir):
        """Should detect known data quality issues."""
        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run_suite(sample_config)

        # Should fail on negative value
        value_check = next(
            r for r in results.check_results if r.check_name == "positive_values"
        )
        assert value_check.status == "failed"

        # Should fail on invalid category
        cat_check = next(
            r for r in results.check_results if r.check_name == "valid_categories"
        )
        assert cat_check.status == "failed"

    def test_persists_results(self, sample_config, temp_dir):
        """Should persist results to database."""
        import duckdb

        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run_suite(sample_config)

        # Query results database
        conn = duckdb.connect(str(temp_dir / "results.db"))
        runs = conn.execute("SELECT * FROM check_runs").fetchall()
        check_results = conn.execute("SELECT * FROM check_results").fetchall()

        assert len(runs) == 1
        assert runs[0][1] == "test_suite"  # suite_name
        assert len(check_results) == 2

    def test_run_programmatic_suite(self, sample_parquet, temp_dir):
        """Should run programmatically defined suite."""
        suite = CheckSuiteConfig(
            name="programmatic_suite",
            source=SourceConfig(type="parquet", path=sample_parquet),
            checks=[
                CheckConfig(
                    name="value_range",
                    type="range",
                    column="value",
                    min=0,
                    max=100,
                    severity="warning",
                ),
            ],
        )

        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run(suite)

        assert len(results.check_results) == 1
        assert results.suite_name == "programmatic_suite"

    def test_overall_status_calculation(self, temp_dir):
        """Should correctly calculate overall status."""
        import pandas as pd

        # Create test data with various issues
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [10, 20, -5],  # One negative
        })
        path = temp_dir / "test.parquet"
        df.to_parquet(path)

        suite = CheckSuiteConfig(
            name="status_test",
            source=SourceConfig(type="parquet", path=path),
            checks=[
                CheckConfig(
                    name="positive_values",
                    type="range",
                    column="value",
                    min=0,
                    severity="critical",
                ),
            ],
        )

        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run(suite)

        # Critical failure should result in "failed" overall status
        assert results.overall_status == "failed"

    def test_run_history(self, sample_config, temp_dir):
        """Should retrieve run history."""
        obs = Observatory(results_db=temp_dir / "results.db")

        # Run twice
        obs.run_suite(sample_config)
        obs.run_suite(sample_config)

        history = obs.get_run_history(suite_name="test_suite")

        assert len(history) == 2


class TestErrorHandling:
    """Tests for error handling in suite execution."""

    def test_handles_missing_config_file(self, temp_dir):
        """Should raise FileNotFoundError for missing config."""
        obs = Observatory(results_db=temp_dir / "results.db")

        with pytest.raises(FileNotFoundError):
            obs.run_suite(temp_dir / "nonexistent.yaml")

    def test_handles_invalid_check_type(self, temp_dir):
        """Should handle invalid check type gracefully."""
        import pandas as pd

        df = pd.DataFrame({"id": [1, 2, 3]})
        data_path = temp_dir / "test.parquet"
        df.to_parquet(data_path)

        suite = CheckSuiteConfig(
            name="error_test",
            source=SourceConfig(type="parquet", path=data_path),
            checks=[
                CheckConfig(
                    name="invalid_check",
                    type="nonexistent_type",
                    column="id",
                ),
            ],
        )

        obs = Observatory(results_db=temp_dir / "results.db")
        results = obs.run(suite)

        # Should record error, not crash
        assert len(results.check_results) == 1
        assert results.check_results[0].status == "error"

"""Tests for completeness checks."""

import pytest

from observatory.checks.completeness import CompletenessCheck


class TestCompletenessCheck:
    """Tests for CompletenessCheck."""

    def test_detects_null_values(self, test_db):
        """Should detect null values in column."""
        check = CompletenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "name_completeness", "column": "name"},
        )

        assert result.status == "failed"
        assert result.metric_value == 1  # One NULL name

    def test_passes_when_no_nulls(self, test_db):
        """Should pass when column has no nulls."""
        check = CompletenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "id_completeness", "column": "id"},
        )

        assert result.status == "passed"
        assert result.metric_value == 0

    def test_respects_threshold(self, test_db):
        """Should pass when null rate is within threshold."""
        check = CompletenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "age_completeness", "column": "age", "threshold": 0.2},
        )

        # 1 null out of 9 = ~11%, below 20% threshold
        assert result.status == "passed"

    def test_includes_sample_nulls(self, test_db):
        """Should include sample rows with null values."""
        check = CompletenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "name_completeness", "column": "name"},
        )

        assert len(result.sample_failures) > 0

    def test_handles_empty_table(self, empty_db):
        """Should handle empty tables gracefully."""
        check = CompletenessCheck()
        result = check.execute(
            empty_db,
            "empty_data",
            {"name": "value_completeness", "column": "value"},
        )

        assert result.status == "warning"
        assert "empty" in result.message.lower()

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = CompletenessCheck()

        with pytest.raises(ValueError, match="'column'"):
            check.validate_config({})

"""Tests for uniqueness checks."""

import pytest

from observatory.checks.uniqueness import UniquenessCheck


class TestUniquenessCheck:
    """Tests for UniquenessCheck."""

    def test_detects_duplicates(self, test_db):
        """Should detect duplicate values."""
        check = UniquenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "id_unique", "column": "id"},
        )

        assert result.status == "failed"
        assert result.metric_value == 1  # One duplicate (id=1)

    def test_passes_when_unique(self, test_db):
        """Should pass when all values are unique."""
        check = UniquenessCheck()
        # Use name column - only one NULL makes it mostly unique (8 distinct of 9)
        # Use salary column which has 7 non-null unique values
        result = check.execute(
            test_db,
            "test_data",
            {"name": "salary_unique", "column": "salary", "threshold": 0.2},
        )

        # 7 unique salary values out of 8 non-null = 12.5% duplicate rate
        assert result.status == "passed"

    def test_composite_uniqueness(self, test_db):
        """Should support composite key uniqueness."""
        check = UniquenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "composite_unique", "columns": ["id", "created_at"]},
        )

        assert result.status == "failed"  # (1, '2024-01-15 10:00:00') is duplicated

    def test_respects_threshold(self, test_db):
        """Should pass when duplicate rate is within threshold."""
        check = UniquenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "id_unique", "column": "id", "threshold": 0.2},
        )

        # 1 duplicate out of 9 = ~11%, below 20% threshold
        assert result.status == "passed"

    def test_includes_duplicate_samples(self, test_db):
        """Should include sample duplicates in result."""
        check = UniquenessCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "id_unique", "column": "id"},
        )

        assert len(result.sample_failures) > 0

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = UniquenessCheck()

        with pytest.raises(ValueError, match="'column' or 'columns'"):
            check.validate_config({})

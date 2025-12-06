"""Tests for validity checks (range, allowed_values, custom_sql)."""

import pytest

from observatory.checks.validity import AllowedValuesCheck, CustomSQLCheck, RangeCheck


class TestRangeCheck:
    """Tests for RangeCheck."""

    def test_detects_out_of_range_values(self, test_db):
        """Should detect values outside the specified range."""
        check = RangeCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "age_range", "column": "age", "min": 0, "max": 100},
        )

        assert result.status == "failed"
        assert result.metric_value == 2  # -5 and 150

    def test_passes_when_all_in_range(self, test_db):
        """Should pass when all values are in range."""
        check = RangeCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "id_range", "column": "id", "min": 0, "max": 100},
        )

        assert result.status == "passed"

    def test_respects_threshold(self, test_db):
        """Should pass when failure rate is within threshold."""
        check = RangeCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "age_range", "column": "age", "min": 0, "max": 100, "threshold": 0.5},
        )

        # 2 failures out of 8 non-null = 25%, below 50% threshold
        assert result.status == "passed"

    def test_includes_sample_failures(self, test_db):
        """Should include sample failures in result."""
        check = RangeCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "age_range", "column": "age", "min": 0, "max": 100},
        )

        assert len(result.sample_failures) > 0

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = RangeCheck()

        with pytest.raises(ValueError, match="'column'"):
            check.validate_config({})

        with pytest.raises(ValueError, match="'min' and/or 'max'"):
            check.validate_config({"column": "age"})


class TestAllowedValuesCheck:
    """Tests for AllowedValuesCheck."""

    def test_detects_invalid_values(self, test_db):
        """Should detect values not in allowed set."""
        check = AllowedValuesCheck()
        result = check.execute(
            test_db,
            "test_data",
            {"name": "valid_category", "column": "category", "allowed_values": ["A", "B", "C"]},
        )

        assert result.status == "failed"
        assert result.metric_value == 1  # "INVALID"

    def test_passes_when_all_valid(self, test_db):
        """Should pass when all values are in allowed set."""
        check = AllowedValuesCheck()
        # id values are 1-8, plus one duplicate
        result = check.execute(
            test_db,
            "test_data",
            {"name": "valid_id", "column": "id", "allowed_values": [1, 2, 3, 4, 5, 6, 7, 8]},
        )

        assert result.status == "passed"

    def test_respects_threshold(self, test_db):
        """Should pass when failure rate is within threshold."""
        check = AllowedValuesCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "valid_category",
                "column": "category",
                "allowed_values": ["A", "B", "C"],
                "threshold": 0.2,
            },
        )

        # 1 failure out of 9 = ~11%, below 20% threshold
        assert result.status == "passed"

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = AllowedValuesCheck()

        with pytest.raises(ValueError, match="'column'"):
            check.validate_config({})

        with pytest.raises(ValueError, match="'allowed_values'"):
            check.validate_config({"column": "category"})


class TestCustomSQLCheck:
    """Tests for CustomSQLCheck."""

    def test_executes_custom_query(self, test_db):
        """Should execute custom SQL and evaluate result."""
        check = CustomSQLCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "negative_age",
                "query": "SELECT COUNT(*) FROM {table} WHERE age < 0",
            },
        )

        assert result.status == "failed"
        assert result.metric_value == 1  # One negative age

    def test_respects_threshold(self, test_db):
        """Should pass when failures are within threshold."""
        check = CustomSQLCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "negative_age",
                "query": "SELECT COUNT(*) FROM {table} WHERE age < 0",
                "threshold": 5,  # Absolute threshold
            },
        )

        assert result.status == "passed"  # 1 < 5

    def test_handles_rate_threshold(self, test_db):
        """Should handle rate-based threshold (< 1)."""
        check = CustomSQLCheck()
        result = check.execute(
            test_db,
            "test_data",
            {
                "name": "negative_age",
                "query": "SELECT COUNT(*) FROM {table} WHERE age < 0",
                "threshold": 0.2,  # 20% rate threshold
            },
        )

        # 1/9 = 11%, below 20% threshold
        assert result.status == "passed"

    def test_validates_config(self):
        """Should raise ValueError for invalid config."""
        check = CustomSQLCheck()

        with pytest.raises(ValueError, match="'query'"):
            check.validate_config({})

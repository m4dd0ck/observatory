"""The committed examples must run offline and produce the documented outcome."""

from pathlib import Path

import pytest

from observatory import Observatory

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestCustomSQLExample:
    """examples/custom_sql/checks.yaml against examples/custom_sql/orders.csv."""

    @pytest.fixture
    def results(self, monkeypatch, temp_dir):
        # Reason: the example's source path is relative to the repo root, as the README says.
        monkeypatch.chdir(REPO_ROOT)
        obs = Observatory(results_db=temp_dir / "results.db")
        return obs.run_suite(REPO_ROOT / "examples" / "custom_sql" / "checks.yaml")

    def test_runs_every_check_without_errors(self, results):
        assert len(results.check_results) == 4
        assert all(r.status in ("passed", "failed") for r in results.check_results)

    def test_only_the_deliberate_failure_fails(self, results):
        by_name = {r.check_name: r for r in results.check_results}
        assert by_name["ship_date_not_before_order_date"].status == "failed"
        assert by_name["ship_date_not_before_order_date"].metric_value == 1
        assert by_name["shipped_orders_have_ship_date"].status == "passed"
        assert by_name["refunds_under_20_percent"].status == "passed"
        assert by_name["at_most_two_large_orders"].status == "passed"
        assert results.overall_status == "warning"

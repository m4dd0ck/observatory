"""Sample failures carry raw column values; every type DuckDB returns must survive json.dumps."""

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import duckdb
import pytest

from observatory.models.results import CheckResult, RunResult
from observatory.storage.duckdb_store import DuckDBStore, json_serializer


def test_serializer_covers_duckdb_value_types():
    values = {
        "d": date(2026, 10, 7),
        "dt": datetime(2026, 10, 7, 11, 3, tzinfo=UTC),
        "t": time(11, 3),
        "td": timedelta(hours=1, minutes=30),
        "dec": Decimal("12.50"),
        "u": UUID(int=1),
        "b": b"\x01\xff",
    }
    out = json.loads(json.dumps(values, default=json_serializer))
    assert out == {
        "d": "2026-10-07",
        "dt": "2026-10-07T11:03:00+00:00",
        "t": "11:03:00",
        "td": 5400.0,
        "dec": 12.5,
        "u": "00000000-0000-0000-0000-000000000001",
        "b": "01ff",
    }
    with pytest.raises(TypeError):
        json.dumps({"x": object()}, default=json_serializer)


def test_save_run_with_date_and_decimal_sample_failures(tmp_path: Path):
    store = DuckDBStore(tmp_path / "results.db")
    run = RunResult(
        suite_name="orders",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_seconds=0.1,
        check_results=[
            CheckResult(
                check_name="amount_range",
                check_type="range",
                status="failed",
                severity="warning",
                message="1 outside range",
                sample_failures=[{"order_date": date(2026, 10, 7), "amount": Decimal("99.90")}],
            )
        ],
    )
    store.save_run(run)
    con = duckdb.connect(str(tmp_path / "results.db"), read_only=True)
    try:
        saved = con.execute("SELECT sample_failures FROM check_results").fetchone()
    finally:
        con.close()
    assert saved is not None
    assert json.loads(saved[0]) == [{"order_date": "2026-10-07", "amount": 99.9}]

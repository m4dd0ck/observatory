# Observatory

YAML-configured data quality checks for parquet, CSV, DuckDB and SQLite tables. DuckDB runs the queries, Pydantic validates the config, Typer and Rich make the CLI, Streamlit and Plotly make the dashboard.

## Why This Exists

Data pipelines break silently. You load data, transform it, build dashboards - then someone notices the numbers look weird and you spend hours tracing it back to a column that started coming in null two weeks ago.

Observatory runs checks against your data and tells you when something's wrong. Inspired by Great Expectations but smaller - no platform to stand up when you just want to validate some tables.

## Quick Start

```bash
git clone https://github.com/m4dd0ck/observatory.git
cd observatory
uv sync

# see what check types exist
uv run observatory list-checks

# run a suite (config format below)
uv run observatory check checks.yaml
```

Every run is saved to `observatory.db` in the current directory. Pass `--db path.db` to put it somewhere else.

Two examples ship with the repo:

- `examples/custom_sql/checks.yaml` runs offline against the eight-row `examples/custom_sql/orders.csv` next to it. Run it from the repo root: `uv run observatory check examples/custom_sql/checks.yaml`. One check fails on purpose.
- `examples/nyc_taxi/checks.yaml` expects `data/yellow_tripdata_2024-01.parquet`, which is not in the repo. Download the January 2024 Yellow Taxi file from the NYC TLC trip record page into `data/` before running it.

## Example Config

A suite has one `source` and a list of `checks`. This is the config used for the output below.

```yaml
# checks.yaml
name: sales_quality
source:
  type: parquet
  path: data/sales.parquet

checks:
  - name: revenue_not_null
    type: completeness
    column: revenue
    threshold: 0.01  # max null rate: fail if more than 1% of rows are null

  - name: revenue_non_negative
    type: range
    column: revenue
    min: 0
    severity: critical

  - name: unique_order_ids
    type: uniqueness
    columns: [order_id]

  - name: valid_status
    type: allowed_values
    column: status
    allowed_values: [pending, shipped, delivered, cancelled]

  - name: orders_are_recent
    type: freshness
    column: order_date
    max_age_hours: 48
```

`source.type` is one of `csv`, `parquet`, `duckdb`, `sqlite`. File sources take `path`; `duckdb` and `sqlite` take `path` (or `connection_string` for `duckdb`) plus `table`, or a `query` to check a subquery instead of a whole table. Relative paths resolve against the directory you run from.

Each check takes `severity: info | warning | critical` (default `warning`) and `enabled: true | false`. `threshold` is the maximum failure rate the check tolerates and defaults to 0. It is a fraction of all rows for `completeness`, and of non-null rows for `range`, `allowed_values` and `uniqueness`; `custom_sql` is the exception, see below.

## Check Types

| Type | Config keys | What It Does |
|------|-------------|--------------|
| `completeness` | `column`, `threshold` | Fails if the null rate is above `threshold` |
| `uniqueness` | `columns` (or `column`), `threshold` | Fails if the duplicate rate for the key is above `threshold` |
| `freshness` | `column` (or `timestamp_column`), `max_age_hours` | Fails if `MAX(column)` is older than `max_age_hours`, measured against the current UTC time |
| `range` | `column`, `min` and/or `max`, `threshold` | Fails if the share of out-of-range values is above `threshold` |
| `allowed_values` | `column`, `allowed_values`, `threshold` | Fails if the share of values outside the set is above `threshold` |
| `schema` | `columns` (list of `name`, `dtype`, `nullable`, or plain names) | Checks columns exist, and when `dtype` is given that the DuckDB type matches. Type matching is lenient: `INTEGER` accepts `BIGINT`, `VARCHAR` accepts `TEXT` |
| `custom_sql` | `query`, `threshold` | Runs your query with `{table}` substituted; the first column is the failure count. `threshold` below 1 is a rate, 1 or more is an absolute count |

## Example Output
### custom_sql

Write any SQL that returns the number of bad rows in its first column. `{table}` is replaced with the source's table expression (for a parquet file that is `read_parquet('path')`), so you can query the source without knowing how it was loaded.

```yaml
  - name: ship_date_not_before_order_date
    type: custom_sql
    query: |
      SELECT COUNT(*) FROM {table}
      WHERE ship_date < order_date

  - name: refunds_under_20_percent
    type: custom_sql
    threshold: 0.2
    query: |
      SELECT COUNT(*) FROM {table}
      WHERE status = 'refunded'
```

Pass/fail: with `threshold` below 1 (the default is 0) the count is divided by `SELECT COUNT(*) FROM {table}` and compared as a rate. With `threshold` of 1 or more the count itself must not exceed it. A query that returns no rows is an `error`; a first column that is not numeric counts as 0 failures. The full runnable version is `examples/custom_sql/checks.yaml`.


```
$ uv run observatory check checks.yaml

╭───────────────────────── Data Quality Check Results ─────────────────────────╮
│ sales_quality                                                                │
│ Status: WARNING                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
        Summary
┏━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric       ┃ Count ┃
┡━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Checks │     5 │
│ Passed       │     4 │
│ Warnings     │     0 │
│ Failed       │     1 │
│ Errors       │     0 │
│ Duration     │ 0.04s │
└──────────────┴───────┘

Failed Checks:
  x [WARNING] unique_order_ids: Found 120 duplicate rows (1.19%) for '(order_id)'
```

`--verbose` adds a per-check table and up to three sample failing rows per check. `--format json` prints the full result as JSON; `--output results.json` writes it to a file instead (and implies JSON).

The exit code tells CI what happened: `0` all passed, `1` a non-critical check failed, `2` a critical check failed, `3` a check errored or the config was invalid. A config path that does not exist is a usage error and exits `2` before any check runs.

## Run History

Results accumulate in DuckDB, so you can see how a suite has been doing:

```
$ uv run observatory history --db results.db --suite sales_quality --limit 1

                                  Run History
┏━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Run ID   ┃ Suite        ┃ Status ┃ Passed ┃ Failed ┃ Duration ┃ Started At   ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ 1b1c7a42 │ sales_quali… │  WARN  │      4 │      1 │    0.04s │ 2026-10-07   │
│          │              │        │        │        │          │ 11:08:04     │
└──────────┴──────────────┴────────┴────────┴────────┴──────────┴──────────────┘
```

## Dashboard

A Streamlit app with overview, trends, failures and coverage pages over the same database:

```bash
uv run observatory dashboard --db results.db --port 8501
```

That shells out to `streamlit run dashboard/app.py --server.port 8501 -- --db results.db`, which also works directly.

## CLI Commands

```bash
observatory check <config.yaml> [--db PATH] [--format console|json] [--output PATH] [--verbose]
observatory history [--db PATH] [--suite NAME] [--limit N]
observatory list-checks
observatory dashboard [--db PATH] [--port N]
```

## Using in Python

```python
from observatory import Observatory

obs = Observatory(results_db="results.db")
result = obs.run_suite("checks.yaml")

print(result.overall_status)  # passed | warning | failed | error
for check in result.check_results:
    print(f"{check.check_name}: {check.status}")
    if check.status == "failed":
        print(f"  {check.message}")
```

### Embedding observatory in Python

`Observatory.run(CheckSuiteConfig)` takes a config object instead of a path. This is how sourcewatch, a status page for public datasets, runs value checks over each probe's sample: build the suite in code, point the source at a parquet file, and translate the `CheckResult`s into its own outcomes.

```python
from pathlib import Path

from observatory import CheckConfig, CheckSuiteConfig, Observatory, SourceConfig

suite = CheckSuiteConfig(
    name="usgs-earthquakes-sample",
    source=SourceConfig(type="parquet", path=Path("sample.parquet")),
    checks=[CheckConfig(name="plausible_magnitude", type="range", column="mag", min=-2, max=10)],
)
result = Observatory(results_db=Path("observatory.db")).run(suite)
for r in result.check_results:
    print(r.check_name, r.status, r.metric_value, r.threshold, r.sample_failures[:3])
```

Every run is written to `results_db` (its directory must already exist), so point it at a scratch location if you keep your own history. `CheckConfig(**d)` accepts the same keys as a YAML check entry.

## Project Structure

```
observatory/
├── checks/          # one module per check type, plus the registry
├── connectors/      # source -> DuckDB table expression
├── models/          # Pydantic config and result models
├── reporters/       # console (Rich) and JSON output
├── storage/         # DuckDB result store
├── cli.py           # Typer commands
└── main.py          # Observatory class: load config, run checks, save results

dashboard/
└── app.py           # Streamlit dashboard
```

## Development

```bash
uv sync --dev
uv run ruff check
uv run mypy observatory/
uv run pytest
```

## Roadmap

- [ ] Postgres connector
- [ ] Slack/email alerting
- [ ] Statistical checks (distribution drift, outliers)
- [ ] Scheduling integration (cron, Airflow)
- [ ] HTML report export

## Background

Built this because Great Expectations felt like overkill for my use cases. I just wanted to run some checks and get notified when things break. The YAML config approach is borrowed from dbt's schema tests - define what you expect, run it, see what failed.

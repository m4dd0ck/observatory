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

The bundled example at `examples/nyc_taxi/checks.yaml` expects `data/yellow_tripdata_2024-01.parquet`, which is not in the repo. Download the January 2024 Yellow Taxi file from the NYC TLC trip record page into `data/` before running it.

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

`source.type` is one of `csv`, `parquet`, `duckdb`, `sqlite`. File sources take `path`; `duckdb` and `sqlite` take `path` plus `table`, or a `query` to check a subquery instead of a whole table.

Each check takes `severity: info | warning | critical` (default `warning`) and `enabled: true | false`. `threshold` is the maximum failure rate the check tolerates, as a fraction of rows, and defaults to 0.

## Check Types

| Type | Config keys | What It Does |
|------|-------------|--------------|
| `completeness` | `column`, `threshold` | Fails if the null rate is above `threshold` |
| `uniqueness` | `columns` (or `column`), `threshold` | Fails if the duplicate rate for the key is above `threshold` |
| `freshness` | `column`, `max_age_hours` | Fails if `MAX(column)` is older than `max_age_hours` |
| `range` | `column`, `min` and/or `max`, `threshold` | Fails if the share of out-of-range values is above `threshold` |
| `allowed_values` | `column`, `allowed_values`, `threshold` | Fails if the share of values outside the set is above `threshold` |
| `schema` | `columns` (list of `name`, `dtype`, `nullable`) | Checks columns exist with the expected DuckDB types |
| `custom_sql` | `query`, `threshold` | Runs your query with `{table}` substituted; the first column is the failure count. `threshold` below 1 is a rate, 1 or more is an absolute count |

## Example Output

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

`--verbose` adds a per-check table and up to three sample failing rows per check. `--format json` prints the full result as JSON; `--output results.json` writes it to a file instead.

The exit code tells CI what happened: `0` all passed, `1` a non-critical check failed, `2` a critical check failed, `3` a check errored or the config could not be loaded.

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

That shells out to `streamlit run dashboard/app.py -- --db results.db`, which also works directly.

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

`Observatory.run(CheckSuiteConfig)` takes a config object instead of a path if you build suites in code.

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

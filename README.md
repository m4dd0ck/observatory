# Observatory

Data quality monitoring framework for catching bad data before it causes problems downstream.

## Why This Exists

Data pipelines break silently. You load data, transform it, build dashboards - then someone notices the numbers look weird and you spend hours tracing it back to a column that started coming in null two weeks ago.

Observatory runs checks against your data and tells you when something's wrong. Inspired by Great Expectations but simpler - no need for a whole platform when you just want to validate some tables.

## Quick Start

```bash
# install
git clone https://github.com/m4dd0ck/observatory.git
cd data-quality-observatory
uv sync

# run checks against a config file
uv run observatory run examples/nyc_taxi/checks.yaml

# or check a single table quickly
uv run observatory check data/sales.parquet --completeness --columns revenue,customer_id
```

## Example Config

```yaml
# checks.yaml
sources:
  sales:
    type: parquet
    path: data/sales.parquet

checks:
  - name: revenue_not_null
    source: sales
    type: completeness
    column: revenue
    threshold: 0.99  # allow 1% nulls

  - name: valid_order_date
    source: sales
    type: freshness
    column: order_date
    max_age_hours: 48  # data shouldn't be older than 2 days

  - name: unique_order_ids
    source: sales
    type: uniqueness
    columns: [order_id]

  - name: valid_status
    source: sales
    type: allowed_values
    column: status
    values: [pending, shipped, delivered, cancelled]
```

## Check Types

| Type | What It Does |
|------|--------------|
| `completeness` | Checks for nulls/missing values |
| `uniqueness` | Checks for duplicate rows |
| `freshness` | Checks if data is recent enough |
| `range` | Checks numeric values are within bounds |
| `allowed_values` | Checks values are in a set |
| `schema` | Checks columns exist with expected types |
| `custom_sql` | Run your own validation query |

## Example Output

```
$ uv run observatory run checks.yaml

Observatory Check Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ revenue_not_null          PASSED  (99.7% complete)
✓ valid_order_date          PASSED  (max age: 6 hours)
✗ unique_order_ids          FAILED  (1,247 duplicates)
✓ valid_status              PASSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3 passed, 1 failed

Failed Check Details:
  unique_order_ids: Found 1,247 duplicate order_id values
    Examples: ORD-1234 (3x), ORD-5678 (2x), ORD-9012 (2x)
```

## Storing Results

Observatory can save check results to DuckDB for trending over time:

```bash
# run checks and store results
uv run observatory run checks.yaml --store observatory.db

# view history
uv run observatory history --db observatory.db --days 7
```

## Dashboard

There's a simple Streamlit dashboard for browsing results:

```bash
uv run streamlit run dashboard/app.py -- --db observatory.db
```

## CLI Commands

```bash
observatory run <config>       # run all checks in config file
observatory check <file>       # quick check on a single file
observatory history            # view past check runs
observatory list-checks        # show available check types
```

## Using in Python

```python
from observatory.models.config import CheckSuiteConfig
from observatory.main import run_check_suite

config = CheckSuiteConfig.from_yaml("checks.yaml")
results = run_check_suite(config)

for check in results.results:
    print(f"{check.check_name}: {check.status}")
    if check.status == "fail":
        print(f"  {check.message}")
```

## Tech Stack

- **DuckDB** - query engine and result storage
- **Pydantic** - config validation
- **Typer + Rich** - CLI
- **Streamlit** - dashboard
- **PyYAML** - config parsing

## Project Structure

```
observatory/
├── checks/          # check implementations
├── connectors/      # data source connections
├── models/          # pydantic config/result models
├── reporters/       # output formatting (console, json)
├── storage/         # result persistence
├── cli.py           # command line interface
└── main.py          # orchestration

dashboard/
└── app.py           # streamlit dashboard
```

## Roadmap

- [ ] Postgres connector
- [ ] Slack/email alerting
- [ ] Statistical checks (distribution drift, outliers)
- [ ] Scheduling integration (cron, Airflow)
- [ ] HTML report export

## Background

Built this because Great Expectations felt like overkill for my use cases. I just wanted to run some checks and get notified when things break. The YAML config approach is borrowed from dbt's schema tests - define what you expect, run it, see what failed.

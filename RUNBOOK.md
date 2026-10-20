# Runbook

Procedures for observatory. `README.md` describes what each command does; this file says when
to run it and in what order.

## On open

```bash
git status --short
git log -3 --oneline
```

## On close

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy observatory/
uv run pytest -q
```

## Run a suite

1. Write a `checks.yaml` (format in `README.md` §How it works), or use `examples/custom_sql/checks.yaml` from the repo root.
2. `uv run observatory check <config>`; add `--db` to keep the history somewhere other than the current directory.
3. `uv run observatory history --db <path> --suite <name>` to see past runs; `uv run observatory dashboard --db <path>` for the Streamlit view (needs `uv sync --extra dashboard`).

## Release

Conventions in `~/developer/hq/CONVENTIONS.md` §Versioning.

1. Bump `version` in `pyproject.toml` and `__version__` in `observatory/__init__.py` to the same value; `uv lock`.
2. Commit `chore: Release vX.Y.Z`, then `git tag -a vX.Y.Z -m "vX.Y.Z"` and `git push origin main --tags`.
3. `gh release create vX.Y.Z --title "observatory vX.Y.Z" --notes "<what changed>"`; include the compare link to the previous tag and mark it latest.
4. CI must be green on the tagged commit (lint, types, tests, the wheel-contents check).
5. sourcewatch pins this package by tag: bump the pin in its `pyproject.toml`, `uv lock` there, and run its tests. The tag in force is recorded in hq (`~/developer/hq/repos.json`).

## Restore on a new machine

1. Clone `git@github.com:m4dd0ck/observatory.git`; `uv sync --all-extras --dev`.
2. Nothing else: no secrets, no data. The `nyc_taxi` example needs the TLC parquet downloaded into `data/` (README §Quick start).

## Validate

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy observatory/
uv run pytest
uv build --wheel
python3 ~/.claude/scripts/doc-check.py --repo .
```

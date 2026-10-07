"""Command-line interface for the Data Quality Observatory."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from observatory.main import Observatory
from observatory.models.config import ObservatorySettings
from observatory.reporters.console import ConsoleReporter
from observatory.reporters.json_reporter import JSONReporter

app = typer.Typer(
    name="observatory",
    help="Data Quality Observatory - Monitor and validate your data quality.",
    add_completion=False,
)

console = Console()


def get_exit_code(overall_status: str) -> int:
    """Get exit code based on run result.

    Exit codes:
    - 0: All checks passed
    - 1: Warnings present
    - 2: Critical failures
    - 3: Errors
    """
    if overall_status == "passed":
        return 0
    elif overall_status == "warning":
        return 1
    elif overall_status == "failed":
        return 2
    else:  # error
        return 3


@app.command("check")
def run_checks(
    config: Annotated[
        Path,
        typer.Argument(
            help="Path to the YAML check configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o",
            help="Path to write JSON output",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Output format: console, json",
        ),
    ] = "console",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed output",
        ),
    ] = False,
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help="Path to results database",
        ),
    ] = None,
) -> None:
    """Run data quality checks from a YAML configuration file."""
    try:
        # FIXME: validate config schema before running
        settings = ObservatorySettings()
        if db:
            settings.results_database = db

        obs = Observatory(settings=settings)
        result = obs.run_suite(config)

        if format == "json" or output:
            json_reporter = JSONReporter(output_path=output)
            json_reporter.report(result)
        else:
            console_reporter = ConsoleReporter(verbose=verbose)
            console_reporter.report(result)

        sys.exit(get_exit_code(result.overall_status))

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(3)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(3)


@app.command("history")
def show_history(
    suite: Annotated[
        str | None,
        typer.Option(
            "--suite", "-s",
            help="Filter by suite name",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit", "-n",
            help="Number of runs to show",
        ),
    ] = 10,
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help="Path to results database",
        ),
    ] = None,
) -> None:
    """Show historical check run results."""
    from rich.table import Table

    settings = ObservatorySettings()
    if db:
        settings.results_database = db

    obs = Observatory(settings=settings)
    runs = obs.get_run_history(suite_name=suite, limit=limit)

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(title="Run History", show_header=True)
    table.add_column("Run ID", style="dim", max_width=8)
    table.add_column("Suite", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Duration", justify="right")
    table.add_column("Started At", style="dim")

    status_colors = {
        "passed": "[green]PASS[/green]",
        "warning": "[yellow]WARN[/yellow]",
        "failed": "[red]FAIL[/red]",
        "error": "[red]ERR[/red]",
    }

    for run in runs:
        table.add_row(
            run["run_id"][:8],  # truncate uuid for display
            run["suite_name"],
            status_colors.get(run["overall_status"], run["overall_status"]),
            str(run["passed_checks"]),
            str(run["failed_checks"]),
            f"{run['duration_seconds']:.2f}s",
            str(run["started_at"])[:19],  # trim off microseconds
        )

    console.print(table)


@app.command("list-checks")
def list_check_types() -> None:
    """List available check types."""
    from rich.table import Table

    from observatory.checks.registry import get_default_registry

    registry = get_default_registry()
    check_types = registry.list_types()

    table = Table(title="Available Check Types", show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Description")

    # TODO: pull these descriptions from the check classes themselves
    descriptions = {
        "schema": "Validates table schema: column presence, types, nullability",
        "completeness": "Fails if a column's null rate is above threshold",
        "range": "Fails if the share of values below min or above max is above threshold",
        "allowed_values": "Fails if the share of values outside the allowed set is above threshold",
        "custom_sql": "Runs your SQL with {table} substituted; first column is the failure count",
        "uniqueness": "Fails if the duplicate rate for a column or key is above threshold",
        "freshness": "Fails if MAX(column) is older than max_age_hours",
    }

    for check_type in check_types:
        table.add_row(check_type, descriptions.get(check_type, ""))

    console.print(table)


@app.command("dashboard")
def launch_dashboard(
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help="Path to results database",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option(
            "--port", "-p",
            help="Port to run dashboard on",
        ),
    ] = 8501,
) -> None:
    """Launch the Streamlit dashboard."""
    import importlib.util
    import subprocess

    if importlib.util.find_spec("streamlit") is None:
        console.print(
            "[red]Error:[/red] Streamlit is not installed. "
            "The dashboard is an optional extra: run [bold]uv sync --extra dashboard[/bold]."
        )
        sys.exit(1)

    dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"

    if not dashboard_path.exists():
        console.print(f"[red]Error:[/red] Dashboard not found at {dashboard_path}")
        sys.exit(1)

    db_path = str(db) if db else "observatory.db"

    console.print(f"[green]Launching dashboard on port {port}...[/green]")
    console.print(f"[dim]Database: {db_path}[/dim]")

    subprocess.run([
        "streamlit", "run", str(dashboard_path),
        "--server.port", str(port),
        "--",
        "--db", db_path,
    ])


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

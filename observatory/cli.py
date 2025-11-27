"""Command-line interface for the Data Quality Observatory."""

# typer makes clis so easy - decorators handle all the argparse stuff
# plus you get nice help text and validation for free

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from observatory.main import Observatory
from observatory.models.config import ObservatorySettings
from observatory.reporters.console import ConsoleReporter
from observatory.reporters.json_reporter import JSONReporter

# main cli app - typer does all the heavy lifting
app = typer.Typer(
    name="observatory",
    help="Data Quality Observatory - Monitor and validate your data quality.",
    add_completion=False,  # shell completion is nice but adds complexity
)

console = Console()


def get_exit_code(overall_status: str) -> int:
    """Get exit code based on run result.

    Exit codes:
    - 0: All checks passed
    - 1: Warnings present (non-critical failures)
    - 2: Critical failures present
    - 3: Execution errors

    these codes are useful for ci/cd - you can fail builds on warnings or only on failures
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
        Optional[Path],
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
        Optional[Path],
        typer.Option(
            "--db",
            help="Path to results database",
        ),
    ] = None,
) -> None:
    """Run data quality checks from a YAML configuration file.

    this is the main command - point it at a yaml file and it'll run all the checks
    """
    try:
        # load settings, override db path if provided
        # FIXME: should probably validate config file schema before running
        settings = ObservatorySettings()
        if db:
            settings.results_database = db

        obs = Observatory(settings=settings)
        result = obs.run_suite(config)

        # Report results
        # json if explicitly requested or if writing to file
        if format == "json" or output:
            json_reporter = JSONReporter(output_path=output)
            json_reporter.report(result)
        else:
            console_reporter = ConsoleReporter(verbose=verbose)
            console_reporter.report(result)

        # Exit with appropriate code
        # lets ci/cd systems know if checks passed or failed
        sys.exit(get_exit_code(result.overall_status))

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(3)
    except Exception as e:
        # catch-all for unexpected errors
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            # show full traceback in verbose mode for debugging
            console.print_exception()
        sys.exit(3)


@app.command("history")
def show_history(
    suite: Annotated[
        Optional[str],
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
        Optional[Path],
        typer.Option(
            "--db",
            help="Path to results database",
        ),
    ] = None,
) -> None:
    """Show historical check run results.

    see how your data quality has changed over time
    """
    # lazy import to speed up cli startup
    from rich.table import Table

    settings = ObservatorySettings()
    if db:
        settings.results_database = db

    obs = Observatory(settings=settings)
    runs = obs.get_run_history(suite_name=suite, limit=limit)

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    # build a nice table showing recent runs
    table = Table(title="Run History", show_header=True)
    table.add_column("Run ID", style="dim", max_width=8)
    table.add_column("Suite", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Duration", justify="right")
    table.add_column("Started At", style="dim")

    # color code the status for quick scanning
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
    """List available check types.

    handy reference for what checks you can use in your yaml config
    """
    # lazy imports keep cli snappy
    from observatory.checks.registry import get_default_registry
    from rich.table import Table

    registry = get_default_registry()
    check_types = registry.list_types()

    table = Table(title="Available Check Types", show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Description")

    # TODO: pull these descriptions from the check classes themselves
    descriptions = {
        "schema": "Validates table schema: column presence, types, nullability",
        "completeness": "Checks for null rates and missing value patterns",
        "range": "Validates values fall within expected numeric range",
        "allowed_values": "Validates values are within an allowed set",
        "custom_sql": "Executes custom SQL query for validation",
        "uniqueness": "Checks for duplicate values in columns",
        "freshness": "Checks data freshness based on timestamp columns",
    }

    for check_type in check_types:
        table.add_row(check_type, descriptions.get(check_type, ""))

    console.print(table)


@app.command("dashboard")
def launch_dashboard(
    db: Annotated[
        Optional[Path],
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
    """Launch the Streamlit dashboard.

    opens a web ui for exploring results - way nicer than staring at json
    """
    import subprocess

    # dashboard lives in a separate directory
    dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"

    if not dashboard_path.exists():
        console.print(f"[red]Error:[/red] Dashboard not found at {dashboard_path}")
        sys.exit(1)

    db_path = str(db) if db else "observatory.db"

    console.print(f"[green]Launching dashboard on port {port}...[/green]")
    console.print(f"[dim]Database: {db_path}[/dim]")

    # streamlit handles all the web server stuff
    # the -- separates streamlit args from our app args
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

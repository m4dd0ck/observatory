"""Rich console reporter for check results."""

# rich makes terminal output look so much better
# tables, colors, panels - all the good stuff

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from observatory.models.results import RunResult
from observatory.reporters.base import BaseReporter


class ConsoleReporter(BaseReporter):
    """Rich console output for check results.

    this is the default reporter - gives you a nice summary table
    and details on any failures. verbose mode shows everything.
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize the reporter.

        Args:
            verbose: Whether to show detailed output.
        """
        self.console = Console()
        self.verbose = verbose

    def report(self, run_result: RunResult) -> None:
        """Generate and output the report."""
        # color coding makes it easy to spot problems at a glance
        status_colors = {
            "passed": "green",
            "warning": "yellow",
            "failed": "red",
            "error": "red",
        }
        status_color = status_colors.get(run_result.overall_status, "white")

        # Header panel
        # big bold header so you know what you're looking at
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]{run_result.suite_name}[/bold]\n"
                f"Status: [{status_color}]{run_result.overall_status.upper()}[/]",
                title="Data Quality Check Results",
            )
        )

        # Summary table
        # quick overview of pass/fail counts
        summary = run_result.summary
        table = Table(title="Summary", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")

        table.add_row("Total Checks", str(summary["total"]))
        table.add_row("Passed", f"[green]{summary['passed']}[/green]")
        table.add_row("Warnings", f"[yellow]{summary['warning']}[/yellow]")
        table.add_row("Failed", f"[red]{summary['failed']}[/red]")
        table.add_row("Errors", f"[red]{summary['error']}[/red]")
        table.add_row("Duration", f"{run_result.duration_seconds:.2f}s")

        self.console.print(table)

        # Individual check results
        # only show the full list in verbose mode, otherwise it's too noisy
        if self.verbose:
            self.console.print()
            results_table = Table(title="Check Results", show_header=True)
            results_table.add_column("Check", style="white")
            results_table.add_column("Type", style="dim")
            results_table.add_column("Status", justify="center")
            results_table.add_column("Message", style="dim")

            for check in run_result.check_results:
                # using text instead of emojis for terminal compatibility
                status_emoji = {
                    "passed": "[green]PASS[/green]",
                    "warning": "[yellow]WARN[/yellow]",
                    "failed": "[red]FAIL[/red]",
                    "error": "[red]ERR[/red]",
                }.get(check.status, check.status)

                results_table.add_row(
                    check.check_name,
                    check.check_type,
                    status_emoji,
                    check.message[:60] + "..." if len(check.message) > 60 else check.message,
                )

            self.console.print(results_table)

        # Failed checks details
        # always show failures, even in non-verbose mode - that's the important stuff
        failures = [r for r in run_result.check_results if r.status in ("failed", "error")]
        if failures:
            self.console.print()
            self.console.print("[bold red]Failed Checks:[/bold red]")
            for check in failures:
                # severity helps prioritize what to fix first
                severity_color = {
                    "critical": "red",
                    "warning": "yellow",
                    "info": "blue",
                }.get(check.severity, "white")

                self.console.print(
                    f"  [red]x[/red] [{severity_color}][{check.severity.upper()}][/] "
                    f"{check.check_name}: {check.message}"
                )

                # sample failures help debug - show actual bad data
                if self.verbose and check.sample_failures:
                    for sample in check.sample_failures[:3]:
                        self.console.print(f"      [dim]Sample: {sample}[/dim]")

        self.console.print()

"""JSON reporter for programmatic consumption."""

# json output is great for piping to other tools, ci/cd, etc
# jq is your friend here

import json
from pathlib import Path
from typing import Any

from observatory.models.results import RunResult
from observatory.reporters.base import BaseReporter


class JSONReporter(BaseReporter):
    """JSON output for programmatic consumption.

    use this when you need to parse the results programmatically,
    or pipe them to another tool. writes to file or stdout.
    """

    def __init__(self, output_path: Path | None = None) -> None:
        """Initialize the reporter.

        Args:
            output_path: Path to write JSON output. If None, prints to stdout.
        """
        self.output_path = output_path

    def report(self, run_result: RunResult) -> None:
        """Generate and output the JSON report."""
        # build up the output dict with all the fields we care about
        output = {
            "run_id": str(run_result.run_id),
            "suite_name": run_result.suite_name,
            "started_at": run_result.started_at.isoformat(),
            "completed_at": run_result.completed_at.isoformat(),
            "duration_seconds": run_result.duration_seconds,
            "overall_status": run_result.overall_status,
            "summary": run_result.summary,
            "metadata": run_result.metadata,
            # flatten out the check results for easier parsing
            "checks": [
                {
                    "check_name": r.check_name,
                    "check_type": r.check_type,
                    "status": r.status,
                    "severity": r.severity,
                    "metric_value": r.metric_value,
                    "threshold": r.threshold,
                    "message": r.message,
                    "details": r.details,
                    "sample_failures": r.sample_failures,
                    "execution_time_ms": r.execution_time_ms,
                }
                for r in run_result.check_results
            ],
        }

        # default=str handles any weird types like uuid, datetime that json doesn't like
        json_str = json.dumps(output, indent=2, default=str)

        if self.output_path:
            # write to file if path provided
            self.output_path.write_text(json_str)
        else:
            # otherwise just dump to stdout
            print(json_str)

    def to_dict(self, run_result: RunResult) -> dict[str, Any]:
        """Convert run result to dictionary without writing.

        useful when you want the dict but don't want to write it anywhere yet
        """
        return {
            "run_id": str(run_result.run_id),
            "suite_name": run_result.suite_name,
            "started_at": run_result.started_at.isoformat(),
            "completed_at": run_result.completed_at.isoformat(),
            "duration_seconds": run_result.duration_seconds,
            "overall_status": run_result.overall_status,
            "summary": run_result.summary,
            # using pydantic's model_dump here for a cleaner conversion
            "checks": [r.model_dump() for r in run_result.check_results],
        }

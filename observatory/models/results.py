"""Result models for check execution."""

from datetime import datetime
from typing import Literal, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Result of a single check execution."""

    # modeled loosely after great expectations' validation result
    # they have way more fields but this covers the basics
    check_name: str
    check_type: str
    status: Literal["passed", "warning", "failed", "error"]  # error = something broke during check
    severity: Literal["info", "warning", "critical"]
    metric_value: float | int | None = None  # the actual measured value
    threshold: float | int | None = None  # what we compared against
    message: str  # human readable explanation
    details: dict[str, Any] = Field(default_factory=dict)  # extra context
    sample_failures: list[dict[str, Any]] = Field(default_factory=list)  # example bad rows
    execution_time_ms: int = 0  # useful for finding slow checks


class RunResult(BaseModel):
    """Complete results of a check run."""

    # this is like a checkpoint result in great expectations
    run_id: UUID = Field(default_factory=uuid4)
    suite_name: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    check_results: list[CheckResult]
    metadata: dict[str, Any] = Field(default_factory=dict)  # env info, git sha, whatever

    @property
    def overall_status(self) -> str:
        """Determine overall status based on check results."""
        # took forever to debug the precedence here
        # errors trump everything, then critical failures, then warnings
        if any(r.status == "error" for r in self.check_results):
            return "error"
        if any(
            r.status == "failed" and r.severity == "critical"
            for r in self.check_results
        ):
            return "failed"
        if any(r.status == "failed" for r in self.check_results):
            return "warning"  # non-critical failures downgrade to warning
        return "passed"

    @property
    def summary(self) -> dict[str, int]:
        """Get summary counts of check statuses."""
        # simple but useful for dashboards and alerts
        return {
            "total": len(self.check_results),
            "passed": sum(1 for r in self.check_results if r.status == "passed"),
            "warning": sum(1 for r in self.check_results if r.status == "warning"),
            "failed": sum(1 for r in self.check_results if r.status == "failed"),
            "error": sum(1 for r in self.check_results if r.status == "error"),
        }

    @property
    def failed_checks(self) -> list[CheckResult]:
        """Get list of failed checks."""
        # handy for quick iteration over what went wrong
        return [r for r in self.check_results if r.status == "failed"]

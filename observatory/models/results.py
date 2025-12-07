"""Result models for check execution."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Result of a single check execution."""

    check_name: str
    check_type: str
    status: Literal["passed", "warning", "failed", "error"]
    severity: Literal["info", "warning", "critical"]
    metric_value: float | int | None = None  # the actual measured value
    threshold: float | int | None = None  # what we compared against
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    sample_failures: list[dict[str, Any]] = Field(default_factory=list)
    execution_time_ms: int = 0


class RunResult(BaseModel):
    """Complete results of a check run."""

    run_id: UUID = Field(default_factory=uuid4)
    suite_name: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    check_results: list[CheckResult]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def overall_status(self) -> str:
        """Determine overall status based on check results."""
        if any(r.status == "error" for r in self.check_results):
            return "error"
        if any(
            r.status == "failed" and r.severity == "critical"
            for r in self.check_results
        ):
            return "failed"
        if any(r.status == "failed" for r in self.check_results):
            return "warning"
        return "passed"

    @property
    def summary(self) -> dict[str, int]:
        """Get summary counts of check statuses."""
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
        return [r for r in self.check_results if r.status == "failed"]

"""Base reporter interface."""

from abc import ABC, abstractmethod

from observatory.models.results import RunResult


class BaseReporter(ABC):
    """Base class for result reporters."""

    @abstractmethod
    def report(self, run_result: RunResult) -> None:
        """Generate and output the report.

        Args:
            run_result: The run result to report.
        """
        pass

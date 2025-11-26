"""Base reporter interface."""

from abc import ABC, abstractmethod

from observatory.models.results import RunResult


class BaseReporter(ABC):
    """Base class for result reporters.

    reporters are pretty simple - they just take a run result and
    output it somewhere. console, json file, slack, whatever.
    """

    @abstractmethod
    def report(self, run_result: RunResult) -> None:
        """Generate and output the report.

        Args:
            run_result: The run result to report.
        """
        # subclasses decide where and how to output
        pass

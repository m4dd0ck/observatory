"""Result reporters for various output formats."""

# reporters take run results and output them in different formats
# TODO: add html reporter for pretty standalone reports
# TODO: add slack reporter for notifications

from observatory.reporters.base import BaseReporter
from observatory.reporters.console import ConsoleReporter
from observatory.reporters.json_reporter import JSONReporter

__all__ = ["BaseReporter", "ConsoleReporter", "JSONReporter"]

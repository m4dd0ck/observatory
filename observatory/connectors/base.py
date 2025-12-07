"""Base connector interface for data sources."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from observatory.models.config import SourceConfig


class BaseConnector(ABC):
    """Abstract base class for data source connectors."""

    @abstractmethod
    def connect(self, config: "SourceConfig") -> duckdb.DuckDBPyConnection:
        """Connect to the data source and return a DuckDB connection.

        Args:
            config: Source configuration with path/connection details.

        Returns:
            DuckDB connection with data accessible.
        """
        pass

    @abstractmethod
    def get_table_name(self, config: "SourceConfig") -> str:
        """Get the table name to use for queries.

        Args:
            config: Source configuration.

        Returns:
            Table name or path to use in SQL queries.
        """
        pass

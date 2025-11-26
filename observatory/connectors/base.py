"""Base connector interface for data sources."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from observatory.models.config import SourceConfig


class BaseConnector(ABC):
    """Abstract base class for data source connectors.

    all connectors return a duckdb connection - we're using duckdb as our
    query engine for everything. it's fast and handles lots of formats natively.
    """

    @abstractmethod
    def connect(self, config: "SourceConfig") -> duckdb.DuckDBPyConnection:
        """Connect to the data source and return a DuckDB connection.

        Args:
            config: Source configuration with path/connection details.

        Returns:
            DuckDB connection with data accessible.
        """
        # subclasses do the actual work here
        pass

    @abstractmethod
    def get_table_name(self, config: "SourceConfig") -> str:
        """Get the table name to use for queries.

        Args:
            config: Source configuration.

        Returns:
            Table name or path to use in SQL queries.
        """
        # this can be a table name, or something like read_parquet('path')
        # duckdb is flexible like that
        pass

"""DuckDB connector for various data sources."""

from pathlib import Path

import duckdb

from observatory.connectors.base import BaseConnector
from observatory.models.config import SourceConfig


class DuckDBConnector(BaseConnector):
    """Connector that uses DuckDB to access various data sources."""

    def __init__(self, memory_limit: str = "2GB") -> None:
        self._memory_limit = memory_limit
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self, config: SourceConfig) -> duckdb.DuckDBPyConnection:
        """Connect to the data source using DuckDB.

        Supports:
        - CSV files
        - Parquet files
        - DuckDB database files
        - SQLite database files
        """
        conn = duckdb.connect(":memory:")
        conn.execute(f"SET memory_limit = '{self._memory_limit}'")

        source_type = config.type.lower()

        if source_type == "parquet":
            pass

        elif source_type == "csv":
            pass

        elif source_type == "duckdb":
            if config.path:
                conn = duckdb.connect(str(config.path), read_only=True)
            elif config.connection_string:
                conn = duckdb.connect(config.connection_string, read_only=True)

        elif source_type == "sqlite":
            if config.path:
                conn.execute(f"ATTACH '{config.path}' AS sqlite_db (TYPE SQLITE)")

        self._conn = conn
        return conn

    def get_table_name(self, config: SourceConfig) -> str:
        """Get the table name/reference for queries."""
        source_type = config.type.lower()

        if source_type == "parquet":
            if config.path:
                path = Path(config.path)
                return f"read_parquet('{path}')"
            elif config.query:
                return f"({config.query})"

        elif source_type == "csv":
            if config.path:
                path = Path(config.path)
                return f"read_csv('{path}', auto_detect=true)"
            elif config.query:
                return f"({config.query})"

        elif source_type in ("duckdb", "sqlite"):
            if config.table:
                if source_type == "sqlite":
                    return f"sqlite_db.{config.table}"
                return config.table
            elif config.query:
                return f"({config.query})"

        raise ValueError(f"Cannot determine table name for source type: {source_type}")

    def close(self) -> None:
        """Close the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

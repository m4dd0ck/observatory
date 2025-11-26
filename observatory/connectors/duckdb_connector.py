"""DuckDB connector for various data sources."""

# duckdb is so nice for this - it can read parquet, csv, sqlite all natively
# no need to load everything into memory first

from pathlib import Path

import duckdb

from observatory.connectors.base import BaseConnector
from observatory.models.config import SourceConfig


class DuckDBConnector(BaseConnector):
    """Connector that uses DuckDB to access various data sources.

    this is the workhorse connector - duckdb can read pretty much anything
    and it's stupid fast for analytics queries.
    """

    def __init__(self, memory_limit: str = "2GB") -> None:
        # 2gb default should be fine for most cases
        # bump it up if you're dealing with big parquet files
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
        # start with an in-memory db, we'll attach sources as needed
        conn = duckdb.connect(":memory:")
        conn.execute(f"SET memory_limit = '{self._memory_limit}'")

        source_type = config.type.lower()

        if source_type == "parquet":
            # Parquet files are read directly via read_parquet
            # Table name will be the file path in quotes
            # don't need to do anything here, duckdb handles it in the query
            pass

        elif source_type == "csv":
            # CSV files are read directly via read_csv
            # same deal - duckdb's auto_detect is pretty good
            pass

        elif source_type == "duckdb":
            # Connect to existing DuckDB database
            # TODO: consider connection pooling for multiple checks
            if config.path:
                conn = duckdb.connect(str(config.path), read_only=True)
            elif config.connection_string:
                conn = duckdb.connect(config.connection_string, read_only=True)

        elif source_type == "sqlite":
            # Attach SQLite database
            # duckdb can query sqlite directly which is pretty slick
            if config.path:
                conn.execute(f"ATTACH '{config.path}' AS sqlite_db (TYPE SQLITE)")

        self._conn = conn
        return conn

    def get_table_name(self, config: SourceConfig) -> str:
        """Get the table name/reference for queries.

        returns something you can put in a FROM clause - either a table name
        or a function call like read_parquet('path/to/file.parquet')
        """
        source_type = config.type.lower()

        if source_type == "parquet":
            # parquet is the best format, fight me
            if config.path:
                path = Path(config.path)
                return f"read_parquet('{path}')"
            elif config.query:
                return f"({config.query})"

        elif source_type == "csv":
            # auto_detect handles headers, types, delimiters etc
            if config.path:
                path = Path(config.path)
                return f"read_csv('{path}', auto_detect=true)"
            elif config.query:
                return f"({config.query})"

        elif source_type in ("duckdb", "sqlite"):
            if config.table:
                # sqlite tables need the db prefix
                if source_type == "sqlite":
                    return f"sqlite_db.{config.table}"
                return config.table
            elif config.query:
                # wrap custom queries in parens so they work as subqueries
                return f"({config.query})"

        raise ValueError(f"Cannot determine table name for source type: {source_type}")

    def close(self) -> None:
        """Close the connection."""
        # always clean up your connections kids
        if self._conn:
            self._conn.close()
            self._conn = None

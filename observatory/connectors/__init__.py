"""Data source connectors."""

# just re-exporting the main connector classes here
# TODO: add postgres connector - that's probably the most requested one
# TODO: add snowflake connector for the enterprise folks

from observatory.connectors.base import BaseConnector
from observatory.connectors.duckdb_connector import DuckDBConnector

__all__ = ["BaseConnector", "DuckDBConnector"]

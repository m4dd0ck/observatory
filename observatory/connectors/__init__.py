"""Data source connectors."""

from observatory.connectors.base import BaseConnector
from observatory.connectors.duckdb_connector import DuckDBConnector

__all__ = ["BaseConnector", "DuckDBConnector"]

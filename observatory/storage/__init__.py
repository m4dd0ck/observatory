"""Storage layer for persisting check results."""

# started with just duckdb, might add more backends later
# great expectations supports a ton of different stores but we'll keep it simple

from observatory.storage.duckdb_store import DuckDBStore

__all__ = ["DuckDBStore"]

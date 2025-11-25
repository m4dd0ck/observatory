"""Data quality check implementations."""

# all the check types we support - standard registry pattern
# add new checks to this list when you create them or you'll wonder
# why they don't show up in the registry (learned this the hard way)

from observatory.checks.base import BaseCheck
from observatory.checks.registry import CheckRegistry, get_default_registry
from observatory.checks.schema import SchemaCheck
from observatory.checks.completeness import CompletenessCheck
from observatory.checks.validity import RangeCheck, AllowedValuesCheck, CustomSQLCheck
from observatory.checks.uniqueness import UniquenessCheck
from observatory.checks.freshness import FreshnessCheck

__all__ = [
    "BaseCheck",
    "CheckRegistry",
    "get_default_registry",
    "SchemaCheck",
    "CompletenessCheck",
    "RangeCheck",
    "AllowedValuesCheck",
    "CustomSQLCheck",
    "UniquenessCheck",
    "FreshnessCheck",
]

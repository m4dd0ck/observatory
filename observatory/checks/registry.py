"""Check registry for managing available check types."""

from typing import TYPE_CHECKING

# avoid circular imports
if TYPE_CHECKING:
    from observatory.checks.base import BaseCheck


class CheckRegistry:
    """Registry of available check types.

    basically a fancy dict that maps check_type strings to check classes.
    could've just used a dict but this gives us nicer error messages.
    """

    def __init__(self) -> None:
        self._checks: dict[str, type[BaseCheck]] = {}

    def register(self, check_class: type["BaseCheck"]) -> type["BaseCheck"]:
        """Register a check class.

        can use this as a decorator too which is pretty slick

        Args:
            check_class: The check class to register.

        Returns:
            The registered check class (allows use as decorator).
        """
        self._checks[check_class.check_type] = check_class
        return check_class

    def get(self, check_type: str) -> type["BaseCheck"]:
        """Get a check class by type name.

        Args:
            check_type: The type of check to retrieve.

        Returns:
            The check class.

        Raises:
            ValueError: If check type is not registered.
        """
        if check_type not in self._checks:
            # actually helpful error message - future you will thank present you
            available = ", ".join(sorted(self._checks.keys()))
            raise ValueError(
                f"Unknown check type: '{check_type}'. Available types: {available}"
            )
        return self._checks[check_type]

    def list_types(self) -> list[str]:
        """List all registered check types."""
        return sorted(self._checks.keys())


# global registry instance - kinda hacky but it works
# TODO: maybe consider dependency injection someday?
_default_registry: CheckRegistry | None = None


def get_default_registry() -> CheckRegistry:
    """Get or create the default check registry with all built-in checks.

    lazy initialization here - don't load all check modules until someone
    actually needs the registry. helps with startup time.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = CheckRegistry()
        # Import and register all built-in checks
        # gotta import here to avoid circular import hell
        from observatory.checks.completeness import CompletenessCheck
        from observatory.checks.freshness import FreshnessCheck
        from observatory.checks.schema import SchemaCheck
        from observatory.checks.uniqueness import UniquenessCheck
        from observatory.checks.validity import (
            AllowedValuesCheck,
            CustomSQLCheck,
            RangeCheck,
        )

        # register em all - order doesn't matter here
        _default_registry.register(SchemaCheck)
        _default_registry.register(CompletenessCheck)
        _default_registry.register(RangeCheck)
        _default_registry.register(AllowedValuesCheck)
        _default_registry.register(CustomSQLCheck)
        _default_registry.register(UniquenessCheck)
        _default_registry.register(FreshnessCheck)

    return _default_registry

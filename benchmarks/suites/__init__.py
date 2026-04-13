"""Suite registry — maps suite names to classes."""

SUITE_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Decorator to register a suite class."""
    SUITE_REGISTRY[cls.name] = cls
    return cls

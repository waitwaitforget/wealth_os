"""Factor registry for discoverability and versioning.

All factors should register themselves at import time so the
system can discover, list, and validate available factors.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from wealth_os.factors.protocol import Factor, FactorCategory, FactorMeta


class FactorRegistry:
    """Global registry of factor implementations.

    Factors register with metadata; the registry provides lookup
    by name, category, or tag.
    """

    _instance: FactorRegistry | None = None
    _factors: dict[str, type[Factor]] = {}
    _instances: dict[str, Factor] = {}

    def __new__(cls) -> FactorRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, factor_cls: type[Factor] | None = None, *, name: str | None = None):
        """Decorator to register a factor class by name.

        Usage:
            @FactorRegistry.register(name="pe_earnings_yield")
            class PEEarningsYieldFactor:
                ...
        """

        def decorator(fc: type[Factor]) -> type[Factor]:
            n = name or fc.__name__
            cls._factors[n] = fc
            return fc

        if factor_cls is not None:
            return decorator(factor_cls)
        return decorator

    @classmethod
    def register_instance(cls, instance: Factor) -> None:
        cls._instances[instance.meta.name] = instance

    @classmethod
    def get(cls, name: str) -> Factor | None:
        if name in cls._instances:
            return cls._instances[name]
        if name in cls._factors:
            instance = cls._factors[name]()
            cls._instances[name] = instance
            return instance
        return None

    @classmethod
    def list_all(cls) -> list[FactorMeta]:
        return [f().meta for f in cls._factors.values()]

    @classmethod
    def list_by_category(cls, category: FactorCategory) -> list[FactorMeta]:
        return [f().meta for f in cls._factors.values() if f().meta.category == category]

    @classmethod
    def list_by_tag(cls, tag: str) -> list[FactorMeta]:
        return [f().meta for f in cls._factors.values() if tag in f().meta.tags]

    @classmethod
    def iter_all(cls) -> Iterator[Factor]:
        for name in list(cls._factors) + list(cls._instances):
            f = cls.get(name)
            if f is not None:
                yield f

    @classmethod
    def clear(cls) -> None:
        cls._factors.clear()
        cls._instances.clear()

    @classmethod
    def summary(cls) -> dict[str, Any]:
        by_cat: dict[str, list[str]] = {}
        for meta in cls.list_all():
            cat = str(meta.category)
            by_cat.setdefault(cat, []).append(meta.name)
        return {
            "total_factors": len(cls._factors),
            "by_category": {k: len(v) for k, v in by_cat.items()},
            "factors": by_cat,
        }

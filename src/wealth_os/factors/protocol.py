"""Factor protocol and metadata.

All factors must implement the ``Factor`` protocol and provide
``FactorMeta`` for discoverability, versioning, and documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

import pandas as pd


class FactorCategory(StrEnum):
    VALUE = "value"
    TREND = "trend"
    RISK = "risk"
    MACRO = "macro"
    SENTIMENT = "sentiment"


class FactorDirection(StrEnum):
    POSITIVE = "positive"  # higher → better
    NEGATIVE = "negative"  # lower → better
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class FactorMeta:
    """Immutable metadata for a factor."""

    name: str
    category: FactorCategory
    description: str = ""
    version: str = "0.1.0"
    direction: FactorDirection = FactorDirection.POSITIVE
    tags: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    input_fields: list[str] = field(default_factory=list)
    output_range: tuple[float, float] = (-3.0, 3.0)
    requires_prices: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": str(self.category),
            "description": self.description,
            "version": self.version,
            "direction": str(self.direction),
            "tags": self.tags,
            "parameters": self.parameters,
            "input_fields": self.input_fields,
            "output_range": list(self.output_range),
            "requires_prices": self.requires_prices,
        }


@runtime_checkable
class Factor(Protocol):
    """Protocol for all factor computations.

    All factors must:
    - Accept a ``pd.DataFrame`` of raw data (prices or metrics)
    - Return a ``pd.DataFrame`` of factor scores with the same index
    - Be stateless (same input → same output, reproducible)
    - Declare ``FactorMeta`` for discoverability
    """

    @property
    def meta(self) -> FactorMeta: ...

    def compute(self, data: pd.DataFrame) -> pd.DataFrame: ...

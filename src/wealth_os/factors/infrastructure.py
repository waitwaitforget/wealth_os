"""Factor infrastructure: caching, snapshots, lineage, market-specific percentile.

Provides production-grade utilities on top of the Factor protocol.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from wealth_os.factors.protocol import Factor

# ── Factor Cache ─────────────────────────────────────────────────


@dataclass
class FactorCache:
    """Simple Parquet-backed factor result cache.

    Cache keys are deterministic (factor name + parameters + input hash).
    """

    cache_dir: Path = Path("data/cache/factors")

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, factor: Factor, data: pd.DataFrame) -> str:
        meta = factor.meta
        payload = {
            "name": meta.name,
            "version": meta.version,
            "params": json.dumps(meta.parameters, sort_keys=True, default=str),
            "input_shape": list(data.shape),
            "input_hash": hashlib.sha256(
                data.to_numpy().tobytes() if hasattr(data, "to_numpy") else b"0"
            ).hexdigest()[:12],
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, factor: Factor, data: pd.DataFrame) -> pd.DataFrame | None:
        key = self._cache_key(factor, data)
        path = self.cache_dir / f"{factor.meta.name}_{key}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None

    def set(self, factor: Factor, data: pd.DataFrame, result: pd.DataFrame) -> None:
        key = self._cache_key(factor, data)
        path = self.cache_dir / f"{factor.meta.name}_{key}.parquet"
        result.to_parquet(path)

    def compute_or_get(self, factor: Factor, data: pd.DataFrame) -> pd.DataFrame:
        cached = self.get(factor, data)
        if cached is not None:
            return cached
        result = factor.compute(data)
        self.set(factor, data, result)
        return result


# ── Factor Snapshot ──────────────────────────────────────────────


@dataclass
class FactorSnapshot:
    """Immutable record of factor computation with lineage."""

    snapshot_id: str
    factor_name: str
    factor_version: str
    created_at: datetime = field(default_factory=datetime.now)
    parameters: dict[str, Any] = field(default_factory=dict)
    input_description: str = ""
    output_path: str = ""
    run_id: str = ""
    code_version: str = "0.1.0"
    data_version: str = ""


def create_snapshot(
    factor: Factor,
    data: pd.DataFrame,
    result: pd.DataFrame,
    output_dir: str | Path,
    run_id: str = "",
    data_version: str = "",
) -> FactorSnapshot:
    """Save a factor computation result as a versioned snapshot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = factor.meta
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"{meta.name}_{ts}"
    output_path = output_dir / f"{snapshot_id}.parquet"

    result.to_parquet(output_path)

    snapshot = FactorSnapshot(
        snapshot_id=snapshot_id,
        factor_name=meta.name,
        factor_version=meta.version,
        parameters=meta.parameters,
        input_description=f"Shape: {data.shape}, range: {data.index[0]} → {data.index[-1]}",
        output_path=str(output_path),
        run_id=run_id,
        data_version=data_version,
    )

    meta_path = output_dir / f"{snapshot_id}.json"
    meta_path.write_text(
        json.dumps(
            {
                "snapshot_id": snapshot.snapshot_id,
                "factor_name": snapshot.factor_name,
                "factor_version": snapshot.factor_version,
                "created_at": snapshot.created_at.isoformat(),
                "parameters": snapshot.parameters,
                "input_description": snapshot.input_description,
                "output_path": snapshot.output_path,
                "run_id": snapshot.run_id,
                "code_version": snapshot.code_version,
                "data_version": snapshot.data_version,
            },
            indent=2,
            default=str,
        )
    )

    return snapshot


# ── Factor Lineage ───────────────────────────────────────────────


@dataclass
class FactorLineageNode:
    """A node in a factor computation DAG."""

    factor_name: str
    factor_version: str
    parameters: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)  # names of upstream factors
    data_version: str = ""
    snapshot_id: str = ""


class FactorLineage:
    """Tracks the chain of factor computations for audit and reproducibility."""

    def __init__(self) -> None:
        self.nodes: dict[str, FactorLineageNode] = {}

    def record(
        self,
        factor: Factor,
        upstream: list[str] | None = None,
        snapshot_id: str = "",
        data_version: str = "",
    ) -> None:
        meta = factor.meta
        self.nodes[meta.name] = FactorLineageNode(
            factor_name=meta.name,
            factor_version=meta.version,
            parameters=meta.parameters,
            inputs=upstream or [],
            data_version=data_version,
            snapshot_id=snapshot_id,
        )

    def lineage_for(self, factor_name: str) -> list[dict[str, Any]]:
        """Return ordered chain from raw data to given factor."""
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()

        def _walk(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            node = self.nodes.get(name)
            if node is None:
                return
            for inp in node.inputs:
                _walk(inp)
            chain.append(
                {
                    "factor": node.factor_name,
                    "version": node.factor_version,
                    "snapshot": node.snapshot_id,
                    "data_version": node.data_version,
                }
            )

        _walk(factor_name)
        return chain


# ── Market-Specific Percentile ────────────────────────────────────


@dataclass
class MarketSpecificPercentileConfig:
    """Configuration for per-market percentile computation."""

    market_key: str  # column suffix, region, or market tag
    lookback: int = 1260


class MarketSpecificPercentile:
    """Compute valuation percentiles separately per market.

    For each market group, compute the rolling historical percentile
    independently, avoiding cross-market contamination.
    """

    def __init__(
        self,
        markets: dict[str, list[str]],  # {market: [instrument_ids]}
        lookback: int = 1260,
    ) -> None:
        self.markets = markets
        self.lookback = lookback

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute per-market historical percentile.

        Args:
            data: DataFrame with instruments as columns.

        Returns:
            DataFrame with same shape, each column's percentile computed
            against its own market group history.
        """
        result = pd.DataFrame(index=data.index, columns=data.columns, dtype=float)

        for _market, instruments in self.markets.items():
            cols = [c for c in instruments if c in data.columns]
            if not cols:
                continue
            subset = data[cols].dropna(how="all")
            if subset.empty:
                continue

            rank = subset.rolling(self.lookback, min_periods=60).rank(pct=True)
            for col in cols:
                if col in rank.columns:
                    result[col] = rank[col]

        return result

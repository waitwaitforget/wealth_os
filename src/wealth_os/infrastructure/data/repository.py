"""Parquet-based data repository with DuckDB query layer.

Implements the ``DataRepository`` protocol using Parquet files for
immutable storage and DuckDB for analytical queries.  Follows the
data layering convention:

    data/
    ├── raw/         raw vendor responses (immutable)
    ├── processed/   canonical bars, instruments, fx
    ├── features/    computed factor features
    └── snapshots/   versioned point-in-time bundles
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from wealth_os.domain.data_models import (
    DataVersion,
    FXRate,
    InstrumentMaster,
    Market,
    MarketDataBundle,
    TradingCalendar,
)


class ParquetRepository:
    """Parquet-based implementation of DataRepository.

    All writes are immutable — data is versioned and never
    silently overwritten.  Supports incremental updates via
    snapshot directories.
    """

    def __init__(
        self,
        root_dir: str | Path,
        duckdb_path: str | Path | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.raw_dir = self.root_dir / "raw"
        self.processed_dir = self.root_dir / "processed"
        self.features_dir = self.root_dir / "features"
        self.snapshots_dir = self.root_dir / "snapshots"

        for d in [self.raw_dir, self.processed_dir, self.features_dir, self.snapshots_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._bar_dir = self.processed_dir / "bars"
        self._instrument_dir = self.processed_dir / "instruments"
        self._fx_dir = self.processed_dir / "fx"
        self._calendar_dir = self.processed_dir / "calendars"

        self._bar_dir.mkdir(parents=True, exist_ok=True)
        self._instrument_dir.mkdir(parents=True, exist_ok=True)
        self._fx_dir.mkdir(parents=True, exist_ok=True)
        self._calendar_dir.mkdir(parents=True, exist_ok=True)

        self._duckdb_path = str(duckdb_path or (self.root_dir / "data.db"))

    def _bar_file(self, instrument_id: str, version: DataVersion) -> Path:
        return self._bar_dir / f"{instrument_id}_{version.version_id}.parquet"

    # ── Bars ────────────────────────────────────────────────────

    def save_bars(self, bars: pd.DataFrame, version: DataVersion) -> None:
        for instrument_id in bars.columns:
            series = bars[instrument_id].dropna()
            if isinstance(series, pd.Series):
                df = series.reset_index()
                df.columns = ["event_time", "close"]
                df["instrument_id"] = instrument_id
                df["source"] = "processed"
                df["data_version"] = version.version_id
                path = self._bar_file(instrument_id, version)
                df.to_parquet(path, index=False)

    def load_bars(
        self,
        instrument_ids: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> pd.DataFrame:
        frames: dict[str, pd.DataFrame] = {}
        for inst in instrument_ids:
            if version is not None:
                path = self._bar_file(inst, version)
                if path.exists():
                    df = pd.read_parquet(path)
                else:
                    continue
            else:
                df = self._load_latest_bar(inst)
                if df is None:
                    continue
            mask = (df["event_time"] >= pd.Timestamp(start)) & (
                df["event_time"] <= pd.Timestamp(end)
            )
            frames[inst] = df.loc[mask, ["event_time", "close"]].set_index("event_time")["close"]

        if not frames:
            return pd.DataFrame()
        result = pd.DataFrame(frames)
        result.index = pd.DatetimeIndex(result.index)
        return result.sort_index()

    def _load_latest_bar(self, instrument_id: str) -> pd.DataFrame | None:
        files = sorted(self._bar_dir.glob(f"{instrument_id}_*.parquet"))
        return pd.read_parquet(files[-1]) if files else None

    # ── Instruments ─────────────────────────────────────────────

    def save_instruments(self, instruments: list[InstrumentMaster], version: DataVersion) -> None:
        rows = [
            {
                "instrument_id": i.instrument_id,
                "symbol": i.symbol,
                "name": i.name,
                "asset_class": str(i.asset_class),
                "market": str(i.market),
                "currency": i.currency,
                "vendor_symbols": json.dumps(i.vendor_symbols),
                "exchange": i.exchange,
                "trading_calendar": i.trading_calendar,
                "lot_size": i.lot_size,
                "price_multiplier": i.price_multiplier,
                "start_date": str(i.start_date) if i.start_date else None,
                "end_date": str(i.end_date) if i.end_date else None,
                "status": str(i.status),
                "data_version": version.version_id,
            }
            for i in instruments
        ]
        pd.DataFrame(rows).to_parquet(
            self._instrument_dir / f"instruments_{version.version_id}.parquet",
            index=False,
        )

    def load_instruments(
        self,
        instrument_ids: list[str] | None = None,
        version: DataVersion | None = None,
    ) -> list[InstrumentMaster]:
        if version is not None:
            p = self._instrument_dir / f"instruments_{version.version_id}.parquet"
            if not p.exists():
                return []
            df = pd.read_parquet(p)
        else:
            files = sorted(self._instrument_dir.glob("instruments_*.parquet"))
            df = pd.read_parquet(files[-1]) if files else pd.DataFrame()

        if df.empty:
            return []

        if instrument_ids is not None:
            df = df[df["instrument_id"].isin(instrument_ids)]

        results: list[InstrumentMaster] = []
        for _, r in df.iterrows():
            results.append(
                InstrumentMaster(
                    instrument_id=str(r["instrument_id"]),
                    symbol=str(r["symbol"]),
                    name=str(r["name"]),
                    asset_class=r["asset_class"],
                    market=Market(str(r["market"])),
                    currency=str(r["currency"]),
                    vendor_symbols=(
                        json.loads(str(r["vendor_symbols"]))
                        if pd.notna(r.get("vendor_symbols"))
                        else {}
                    ),
                    exchange=str(r.get("exchange", "")),
                    trading_calendar=str(r.get("trading_calendar", "")),
                    lot_size=int(r.get("lot_size", 1)),
                )
            )
        return results

    # ── FX Rates ────────────────────────────────────────────────

    def save_fx_rates(self, rates: list[FXRate], version: DataVersion) -> None:
        rows = [
            {
                "base_currency": r.base_currency,
                "quote_currency": r.quote_currency,
                "event_time": r.event_time,
                "rate": r.rate,
                "source": r.source,
                "quality": str(r.quality),
                "data_version": version.version_id,
            }
            for r in rates
        ]
        pd.DataFrame(rows).to_parquet(
            self._fx_dir / f"fx_{version.version_id}.parquet", index=False
        )

    def load_fx_rates(
        self,
        pairs: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> list[FXRate]:
        if version is not None:
            p = self._fx_dir / f"fx_{version.version_id}.parquet"
            df = pd.read_parquet(p) if p.exists() else pd.DataFrame()
        else:
            files = sorted(self._fx_dir.glob("fx_*.parquet"))
            df = pd.read_parquet(files[-1]) if files else pd.DataFrame()

        if df.empty:
            return []

        mask = (df["event_time"] >= pd.Timestamp(start)) & (df["event_time"] <= pd.Timestamp(end))
        pair_set = set(pairs)
        df = df[mask & (df["base_currency"] + "/" + df["quote_currency"]).isin(pair_set)]

        return [
            FXRate(
                base_currency=str(r["base_currency"]),
                quote_currency=str(r["quote_currency"]),
                event_time=r["event_time"],
                rate=float(r["rate"]),
                source=str(r.get("source", "")),
            )
            for _, r in df.iterrows()
        ]

    # ── Trading Calendar ────────────────────────────────────────

    def save_trading_calendar(self, calendar: TradingCalendar, version: DataVersion) -> None:
        rows = [
            {
                "market": str(calendar.market),
                "trading_day": d,
                "timezone": calendar.timezone,
                "data_version": version.version_id,
            }
            for d in sorted(calendar.trading_days)
        ]
        pd.DataFrame(rows).to_parquet(
            self._calendar_dir / f"calendar_{version.version_id}.parquet",
            index=False,
        )

    def load_trading_calendar(
        self, market: Market, version: DataVersion | None = None
    ) -> TradingCalendar | None:
        if version is not None:
            p = self._calendar_dir / f"calendar_{version.version_id}.parquet"
            if not p.exists():
                return None
            df = pd.read_parquet(p)
        else:
            files = sorted(self._calendar_dir.glob("calendar_*.parquet"))
            if not files:
                return None
            df = pd.read_parquet(files[-1])

        if df.empty:
            return None
        df = df[df["market"] == str(market)]
        if df.empty:
            return None
        trading_days = frozenset(pd.Timestamp(d).date() for d in df["trading_day"])
        tz = str(df["timezone"].iloc[0])
        return TradingCalendar(market=market, trading_days=trading_days, timezone=tz)

    # ── Bundle ──────────────────────────────────────────────────

    def load_bundle(
        self,
        instrument_ids: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> MarketDataBundle:
        prices = self.load_bars(instrument_ids, start, end, version)
        return MarketDataBundle(
            prices=prices,
            data_version=version or self.get_latest_version(),
            description=f"Bundle: {len(instrument_ids)} instruments, {start} → {end}",
        )

    # ── Versioning ──────────────────────────────────────────────

    def create_version(
        self,
        instruments: list[InstrumentMaster],
        bars: pd.DataFrame,
        fx_rates: list[FXRate] | None = None,
        calendars: list[TradingCalendar] | None = None,
        source_files: list[str] | None = None,
    ) -> DataVersion:
        version_id = _make_version_id(instruments, bars)

        version = DataVersion(
            version_id=version_id,
            created_at=pd.Timestamp.now(),
            instruments_hash=_hash_objects(instruments),
            bars_hash=_hash_objects(bars),
            fx_hash=_hash_objects(fx_rates or []),
            source_files=source_files or [],
        )

        snapshot_dir = self.snapshots_dir / version_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.save_instruments(instruments, version)
        self.save_bars(bars, version)
        if fx_rates:
            self.save_fx_rates(fx_rates, version)
        if calendars:
            for cal in calendars:
                self.save_trading_calendar(cal, version)

        _write_version_meta(snapshot_dir, version)
        return version

    def list_versions(self) -> list[DataVersion]:
        versions: list[DataVersion] = []
        for d in sorted(self.snapshots_dir.iterdir()):
            meta = d / "version.json"
            if meta.exists():
                with open(meta) as f:
                    data = json.load(f)
                    versions.append(
                        DataVersion(
                            version_id=data["version_id"],
                            created_at=pd.Timestamp(data["created_at"]),
                            instruments_hash=data.get("instruments_hash", ""),
                            bars_hash=data.get("bars_hash", ""),
                        )
                    )
        return versions

    def get_latest_version(self) -> DataVersion | None:
        versions = self.list_versions()
        return versions[-1] if versions else None


# ── DuckDB Query Layer ───────────────────────────────────────────


class DuckDBQuerier:
    """Analytical query layer over the Parquet data store."""

    def __init__(self, repo: ParquetRepository) -> None:
        self.repo = repo
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self.repo._duckdb_path)
        return self._conn

    def query(self, sql: str) -> pd.DataFrame:
        return self.conn.execute(sql).fetchdf()

    def register_parquet(self, table_name: str, path: str | Path) -> None:
        self.conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{path}')"
        )

    def bars_view(self, version_id: str) -> None:
        paths = list(self.repo._bar_dir.glob(f"*_{version_id}.parquet"))
        if paths:
            all_paths = [str(p) for p in paths]
            paths_str = ", ".join(f"'{p}'" for p in all_paths)
            self.conn.execute(
                f"CREATE OR REPLACE VIEW bars AS SELECT * FROM read_parquet([{paths_str}])"
            )

    def instrument_summary(self) -> pd.DataFrame:
        sql = (
            "SELECT instrument_id, COUNT(*) as bar_count, "
            "MIN(event_time) as first, MAX(event_time) as last "
            "FROM bars GROUP BY 1"
        )
        return self.query(sql)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ── Helpers ──────────────────────────────────────────────────────


def _make_version_id(instruments: list[InstrumentMaster], bars: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(str(sorted(i.instrument_id for i in instruments)).encode())
    h.update(str(bars.shape).encode())
    h.update(str(bars.index[0]).encode())
    h.update(str(bars.index[-1]).encode())
    return h.hexdigest()[:12]


def _hash_objects(obj: object) -> str:
    data = json.dumps(str(obj), sort_keys=True, default=str)
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def _write_version_meta(snapshot_dir: Path, version: DataVersion) -> None:
    meta = {
        "version_id": version.version_id,
        "created_at": str(version.created_at),
        "instruments_hash": version.instruments_hash,
        "bars_hash": version.bars_hash,
        "fx_hash": version.fx_hash,
        "source_files": version.source_files,
        "transform_version": version.transform_version,
    }
    with open(snapshot_dir / "version.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)


# ── Incremental update helper ────────────────────────────────────


def merge_bar_frames(
    existing: pd.DataFrame | None,
    new_data: pd.DataFrame,
    on: str = "event_time",
) -> pd.DataFrame:
    """Merge incremental data, keeping latest known values per key.

    If ``existing`` is None, return ``new_data`` as-is.  Otherwise
    concatenate and drop duplicates keeping the latest (new) row.
    """
    if existing is None or existing.empty:
        return new_data.copy()
    combined = pd.concat([existing, new_data])
    needs_reset = combined.index.name or not isinstance(combined.index, pd.RangeIndex)
    combined = combined.reset_index() if needs_reset else combined
    if on not in combined.columns:
        return combined
    return combined.drop_duplicates(subset=[on], keep="last")

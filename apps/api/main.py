"""Wealth OS Dashboard API — FastAPI backend.

Serves portfolio, risk, factor, and decision data to the
Next.js frontend dashboard.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.extended_metrics import extended_metrics, full_performance_report
from wealth_os.analytics.performance import performance_summary
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.backtest.native import NativeBacktestEngine
from wealth_os.domain.models import (
    AssetClass,
    Instrument,
    PortfolioConstraints,
    Sleeve,
    TransactionCostConfig,
    TriggerConfig,
)
from wealth_os.factors.risk import VolatilityEstimator
from wealth_os.factors.trend import TrendFactor
from wealth_os.factors.valuation import ValuationFactor
from wealth_os.infrastructure.data.repository import ParquetRepository

app = FastAPI(title="Wealth OS Dashboard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CASH_SYMBOL = "CASH_CNY"
ASSETS = ["CSI300", "HSI", "SP500", "NASDAQ100", "GOLD", CASH_SYMBOL]
DATA_DIR = "data"


def _get_instruments() -> dict[str, Instrument]:
    return {
        "CSI300": Instrument("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "HSI": Instrument("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
        "SP500": Instrument("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "NASDAQ100": Instrument("NASDAQ100", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "GOLD": Instrument("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
        CASH_SYMBOL: Instrument(CASH_SYMBOL, AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
    }


def _load_prices() -> pd.DataFrame | None:
    try:
        repo = ParquetRepository(root_dir=DATA_DIR)
        instruments = repo.load_instruments()
        if not instruments:
            return None
        ids = [i.instrument_id for i in instruments]
        loaded = repo.load_bars(ids, start=date(2018, 1, 1), end=date(2026, 8, 5))
        if CASH_SYMBOL not in loaded.columns:
            loaded[CASH_SYMBOL] = np.nan
        return loaded[ASSETS]
    except Exception:
        return None


def _run_backtest() -> dict[str, Any] | None:
    prices = _load_prices()
    if prices is None:
        return None

    instruments = _get_instruments()
    base = pd.Series({"CSI300": 0.20, "HSI": 0.12, "SP500": 0.28, "NASDAQ100": 0.10, "GOLD": 0.07, CASH_SYMBOL: 0.23})
    constraints = PortfolioConstraints(
        max_weights={"GOLD": 0.15, "NASDAQ100": 0.25},
        min_weights={CASH_SYMBOL: 0.05},
        sleeve_bounds={Sleeve.CORE: (0.45, 0.90)},
        max_turnover=0.20,
    )

    risky = prices.drop(columns=[CASH_SYMBOL], errors="ignore")
    r1, r2 = np.random.RandomState(1), np.random.RandomState(2)
    vm = {
        "earnings_yield": pd.DataFrame(r1.uniform(-0.02, 0.02, size=risky.shape), index=risky.index, columns=risky.columns) + 0.06,
        "dividend_yield": pd.DataFrame(r2.uniform(-0.005, 0.005, size=risky.shape), index=risky.index, columns=risky.columns) + 0.025,
    }
    val = ValuationFactor({"earnings_yield": 0.7, "dividend_yield": 0.3}, lookback=756).compute(vm).reindex(columns=prices.columns).fillna(0)
    trd = TrendFactor().compute(risky).reindex(columns=prices.columns).fillna(0)
    vol = VolatilityEstimator().compute(risky).reindex(columns=prices.columns).fillna(0)

    alloc = VTRAllocationPolicy(instruments, base, constraints, CASH_SYMBOL, value_weight=0.4, trend_weight=0.4, inverse_vol_weight=0.2, signal_strength=0.3, target_volatility=0.10)
    engine = NativeBacktestEngine(
        allocator=alloc,
        trigger_engine=RebalanceTriggerEngine(TriggerConfig(weight_drift={"GOLD": 0.01})),
        cost_model=TransactionCostModel(TransactionCostConfig(sell_tax_bps=3, fx_bps=3)),
        cash_symbol=CASH_SYMBOL,
        initial_capital=1_000_000,
        initial_deployment_ratio=1.0,
    )
    result = engine.run(prices, val, trd, vol, pd.Series(0, index=prices.index), pd.Series((1.02 ** (1 / 252) - 1), index=prices.index))
    return result


@app.get("/api/v1/portfolio/summary")
async def portfolio_summary() -> dict[str, Any]:
    result = _run_backtest()
    if result is None:
        return {"error": "No data available"}

    perf = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    ext = extended_metrics(result)
    nav = result.nav.dropna()
    return {
        "total_assets": float(nav.iloc[-1]),
        "daily_return": float(nav.pct_change().iloc[-1]) if len(nav) > 1 else 0,
        "twr": perf["twr"],
        "cagr": perf["annualized_return"],
        "volatility": perf["annualized_volatility"],
        "max_drawdown": perf["max_drawdown"],
        "sharpe": perf["sharpe"],
        "sortino": perf["sortino"],
        "calmar": perf["calmar"],
        "cdar_95": ext["cdar_95"],
        "recovery_days": ext["recovery_time_days"],
        "total_orders": len(result.orders) if result.orders is not None else 0,
        "cost_impact_bps": ext["avg_annual_cost_bps"],
    }


@app.get("/api/v1/portfolio/allocations")
async def portfolio_allocations() -> dict[str, Any]:
    result = _run_backtest()
    if result is None:
        return {"error": "No data available"}

    weights = result.actual_weights.iloc[-1]
    nav = float(result.nav.dropna().iloc[-1])
    prices = _load_prices()
    latest_px = prices.iloc[-1] if prices is not None else pd.Series(dtype=float)

    assets = []
    for sym in weights.index:
        w = float(weights[sym])
        if w > 0.001:
            px = float(latest_px.get(sym, 0)) if sym in latest_px.index else 0
            assets.append({
                "symbol": sym,
                "weight": w,
                "value": w * nav,
                "price": px,
                "change_1d": 0.0 if px == 0 else float(prices[sym].pct_change().iloc[-1]) if sym in prices.columns else 0,
            })

    sleeves = {}
    for a in assets:
        s = "CASH" if "CASH" in a["symbol"].upper() else "RISKY"
        sleeves.setdefault(s, 0)
        sleeves[s] += a["weight"]

    return {"assets": assets, "sleeves": sleeves, "total_nav": nav}


@app.get("/api/v1/portfolio/nav-history")
async def nav_history() -> dict[str, Any]:
    result = _run_backtest()
    if result is None:
        return {"error": "No data available"}

    nav = result.unit_nav.dropna()
    history = []
    for ts, val in nav.items():
        history.append({"date": str(ts.date()), "unit_nav": float(val)})

    return {"history": history, "start": str(nav.index[0].date()), "end": str(nav.index[-1].date())}


@app.get("/api/v1/factors/signals")
async def factor_signals(
    date_str: str = Query("latest", alias="date"),
) -> dict[str, Any]:
    prices = _load_prices()
    if prices is None:
        return {"error": "No data available"}

    risky = prices.drop(columns=[CASH_SYMBOL], errors="ignore")
    trd = TrendFactor().compute(risky).fillna(0).iloc[-1]
    vol = VolatilityEstimator().compute(risky).fillna(0).iloc[-1]

    signals = {}
    for sym in risky.columns:
        signals[sym] = {
            "trend": round(float(trd.get(sym, 0)), 3),
            "volatility": round(float(vol.get(sym, 0)), 3),
            "value": 0.0,
            "combined": round(float(trd.get(sym, 0)) * 0.5, 3),
        }

    return {"signals": signals, "date": str(prices.index[-1].date())}


@app.get("/api/v1/risk/metrics")
async def risk_metrics() -> dict[str, Any]:
    result = _run_backtest()
    if result is None:
        return {"error": "No data available"}

    perf = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    ext = extended_metrics(result)

    return {
        "volatility": perf["annualized_volatility"],
        "max_drawdown": perf["max_drawdown"],
        "sharpe": perf["sharpe"],
        "sortino": perf["sortino"],
        "calmar": perf["calmar"],
        "cdar_95": ext["cdar_95"],
        "recovery_days": ext["recovery_time_days"],
        "total_turnover": ext["total_turnover"],
        "cost_impact_pre_post": ext["cost_impact_on_twr"],
    }


@app.get("/api/v1/data/health")
async def data_health() -> dict[str, Any]:
    try:
        repo = ParquetRepository(root_dir=DATA_DIR)
        instruments = repo.load_instruments()
        if not instruments:
            return {"status": "no_data", "assets": {}}

        prices = _load_prices()
        if prices is None:
            return {"status": "no_data"}

        health = {}
        for col in prices.columns:
            s = prices[col].dropna()
            health[col] = {
                "rows": len(s),
                "start": str(s.index[0].date()),
                "end": str(s.index[-1].date()),
                "missing_pct": round(float(prices[col].isna().mean() * 100), 1),
                "ok": prices[col].isna().mean() < 0.10,
            }

        version = repo.get_latest_version()
        return {
            "status": "healthy" if all(v["ok"] for v in health.values()) else "warning",
            "version": version.version_id if version else "unknown",
            "instruments": len(instruments),
            "assets": health,
        }
    except Exception:
        return {"status": "error", "assets": {}}

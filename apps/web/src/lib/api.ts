// API types for Wealth OS Dashboard
export interface PortfolioSummary {
  total_assets: number;
  daily_return: number;
  twr: number;
  cagr: number;
  volatility: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  cdar_95: number;
  recovery_days: number;
  total_orders: number;
  cost_impact_bps: number;
}

export interface AssetAllocation {
  symbol: string;
  weight: number;
  value: number;
  price: number;
  change_1d: number;
}

export interface Allocations {
  assets: AssetAllocation[];
  sleeves: Record<string, number>;
  total_nav: number;
}

export interface NavPoint {
  date: string;
  unit_nav: number;
}

export interface NavHistory {
  history: NavPoint[];
  start: string;
  end: string;
}

export interface FactorSignals {
  signals: Record<string, { trend: number; volatility: number; value: number; combined: number }>;
  date: string;
}

export interface RiskMetrics {
  volatility: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  cdar_95: number;
  recovery_days: number;
  total_turnover: number;
  cost_impact_pre_post: number;
}

export interface AssetHealth {
  rows: number;
  start: string;
  end: string;
  missing_pct: number;
  ok: boolean;
}

export interface DataHealth {
  status: string;
  version: string;
  instruments: number;
  assets: Record<string, AssetHealth>;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  } catch {
    console.warn(`API unavailable at ${BASE_URL}${path}`);
    return null;
  }
}

export const api = {
  portfolioSummary: () => fetchJSON<PortfolioSummary>("/api/v1/portfolio/summary"),
  allocations: () => fetchJSON<Allocations>("/api/v1/portfolio/allocations"),
  navHistory: () => fetchJSON<NavHistory>("/api/v1/portfolio/nav-history"),
  factorSignals: () => fetchJSON<FactorSignals>("/api/v1/factors/signals"),
  riskMetrics: () => fetchJSON<RiskMetrics>("/api/v1/risk/metrics"),
  dataHealth: () => fetchJSON<DataHealth>("/api/v1/data/health"),
};

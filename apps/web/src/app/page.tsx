"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { api } from "@/lib/api";
import type { PortfolioSummary, Allocations, NavHistory, FactorSignals, RiskMetrics, DataHealth, DecisionsResponse } from "@/lib/api";

const COLORS = ["#3b82f6", "#8b5cf6", "#22c55e", "#f59e0b", "#ef4444", "#64748b"];
const SLEEVE_COLORS: Record<string, string> = { CORE: "#3b82f6", SATELLITE: "#8b5cf6", ALTERNATIVE: "#f59e0b", CASH: "#64748b" };

function formatCurrency(v: number) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "CNY", maximumFractionDigits: 0 }).format(v); }
function formatPct(v: number) { return `${(v * 100).toFixed(2)}%`; }
function colorForPct(v: number) { return v >= 0 ? "text-emerald-400" : "text-red-400"; }

// ── Top Bar ──
function TopBar({ summary, health }: { summary: PortfolioSummary | null; health: DataHealth | null }) {
  return (
    <header className="border-b border-[#1e293b] bg-[#111827] px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Wealth OS</h1>
        <p className="text-xs text-[#64748b]">Cash-aware multi-asset operating system</p>
      </div>
      <div className="flex items-center gap-8">
        <div className="text-right">
          <div className="text-2xl font-mono font-bold">{summary ? formatCurrency(summary.total_assets) : "—"}</div>
          {summary && <div className={`text-sm ${colorForPct(summary.daily_return)}`}>{formatPct(summary.daily_return)} today</div>}
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold ${health?.status === "healthy" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
          {health?.status === "healthy" ? "● Data Healthy" : "● Data Warning"}
        </div>
        <div className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400">
          ● Strategy: VTR v1
        </div>
      </div>
    </header>
  );
}

// ── Pie Chart ──
function AssetPie({ allocations }: { allocations: Allocations | null }) {
  if (!allocations) return <Card title="Asset Allocation"><div className="text-[#64748b]">Loading...</div></Card>;
  const data = allocations.assets.filter(a => a.weight > 0.005).map(a => ({ name: a.symbol, value: a.weight * 100, change: a.change_1d }));
  return (
    <Card title="Portfolio Allocation">
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={180} height={180}>
          <PieChart><Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" stroke="none">{data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie></PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex justify-between text-sm">
              <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />{d.name}</span>
              <span className="font-mono">{d.value.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ── NAV Chart ──
function NavChart({ nav }: { nav: NavHistory | null }) {
  if (!nav) return <Card title="NAV History"><div className="text-[#64748b]">Loading...</div></Card>;
  return (
    <Card title="Unit NAV">
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={nav.history}><defs><linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} /><stop offset="100%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient></defs>
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={v => v.slice(2)} />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={v => v.toFixed(2)} />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1e293b", borderRadius: 8, color: "#e2e8f0" }} formatter={(v: unknown) => [`${(v as number).toFixed(4)}`, "Unit NAV"]} />
          <Area type="monotone" dataKey="unit_nav" stroke="#3b82f6" fill="url(#navGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

// ── Risk Dashboard ──
function RiskDash({ risk }: { risk: RiskMetrics | null }) {
  if (!risk) return <Card title="Risk Metrics"><div className="text-[#64748b]">Loading...</div></Card>;
  const items = [
    { label: "Volatility", value: risk.volatility, fmt: (v: number) => formatPct(v), warn: 0.15 },
    { label: "Max Drawdown", value: risk.max_drawdown, fmt: (v: number) => formatPct(v), warn: -0.10 },
    { label: "Sharpe", value: risk.sharpe, fmt: (v: number) => v.toFixed(3), warn: 0 },
    { label: "Sortino", value: risk.sortino, fmt: (v: number) => v.toFixed(3), warn: 0 },
    { label: "CDaR 95%", value: risk.cdar_95, fmt: (v: number) => formatPct(v), warn: -0.08 },
    { label: "Calmar", value: risk.calmar, fmt: (v: number) => v.toFixed(3), warn: 0 },
  ];
  return (
    <Card title="Risk Metrics">
      <div className="space-y-3">
        {items.map(item => (
          <div key={item.label}>
            <div className="flex justify-between text-xs text-[#64748b] mb-1"><span>{item.label}</span><span className="font-mono">{item.fmt(item.value)}</span></div>
            <div className="h-1.5 bg-[#1e293b] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, Math.abs(item.value) * (item.label === "Volatility" ? 500 : 300))}%`, background: item.value > item.warn ? "#22c55e" : "#ef4444" }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Factor Heatmap ──
function FactorHeatmap({ factors }: { factors: FactorSignals | null }) {
  if (!factors) return <Card title="Factor Signals"><div className="text-[#64748b]">Loading...</div></Card>;
  const symbols = Object.keys(factors.signals);
  return (
    <Card title={`Factor Signals — ${factors.date}`}>
      <table className="w-full text-sm">
        <thead><tr className="text-[#64748b] text-xs">{["Asset", "Trend", "Vol", "Value", "Combined"].map(h => <th key={h} className="text-left pb-2">{h}</th>)}</tr></thead>
        <tbody>
          {symbols.map(sym => {
            const s = factors.signals[sym];
            const c = s.combined;
            return (
              <tr key={sym} className="border-t border-[#1e293b]">
                <td className="py-2 font-medium">{sym}</td>
                {["trend", "volatility", "value", "combined"].map(k => {
                  const v = (s as Record<string, number>)[k];
                  return <td key={k} className="py-2 font-mono"><span className={v > 0.5 ? "text-emerald-400" : v < -0.5 ? "text-red-400" : "text-[#64748b]"}>{v.toFixed(2)}</span></td>;
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

// ── Data Health ──
function HealthCard({ health }: { health: DataHealth | null }) {
  if (!health) return <Card title="Data Health"><div className="text-[#64748b]">Loading...</div></Card>;
  return (
    <Card title="Data Health">
      <div className="space-y-2 text-sm">
        {Object.entries(health.assets).map(([sym, h]) => (
          <div key={sym} className="flex justify-between">
            <span>{sym}</span>
            <span className={`font-mono ${h.ok ? "text-emerald-400" : "text-amber-400"}`}>{h.ok ? "OK" : `${h.missing_pct}% missing`}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-[#1e293b] text-xs text-[#64748b] flex justify-between">
        <span>Version: {health.version}</span><span>{health.instruments} instruments</span>
      </div>
    </Card>
  );
}

// ── Decisions Card ──
function DecisionsCard({ decisions }: { decisions: DecisionsResponse | null }) {
  if (!decisions) return <Card title="Latest Decision"><div className="text-[#64748b]">Loading...</div></Card>;
  const { date, n_trades, is_no_action, confidence, est_cost_bps, trigger, trades } = decisions;
  return (
    <Card title={`Latest Decision — ${date}`}>
      {is_no_action ? (
        <div className="text-sm text-[#94a3b8]">
          <span className="text-emerald-400 font-semibold">NO ACTION</span>
          <p className="mt-1 text-xs text-[#64748b]">{trigger.join(", ")}</p>
        </div>
      ) : (
        <div>
          <div className="flex gap-4 text-xs text-[#64748b] mb-3">
            <span>{n_trades} trades</span>
            <span>Confidence: {(confidence * 100).toFixed(0)}%</span>
            <span>Est cost: {est_cost_bps} bps</span>
          </div>
          <div className="space-y-1">
            {trades.map(t => (
              <div key={t.asset} className="flex justify-between text-sm items-center border-t border-[#1e293b] pt-1">
                <span className="font-medium">{t.asset}</span>
                <span className="font-mono text-xs text-[#64748b]">{t.current.toFixed(1)}% → {t.target.toFixed(1)}%</span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded ${t.action === "buy" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{t.action.toUpperCase()} {(t.delta * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#111827] border border-[#1e293b] rounded-xl p-5 hover:border-[#334155] transition-colors">
      <h3 className="text-sm font-semibold text-[#94a3b8] mb-4 uppercase tracking-wide">{title}</h3>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [allocations, setAllocations] = useState<Allocations | null>(null);
  const [nav, setNav] = useState<NavHistory | null>(null);
  const [factors, setFactors] = useState<FactorSignals | null>(null);
  const [risk, setRisk] = useState<RiskMetrics | null>(null);
  const [health, setHealth] = useState<DataHealth | null>(null);
  const [decisions, setDecisions] = useState<DecisionsResponse | null>(null);

  useEffect(() => {
    api.portfolioSummary().then(setSummary).catch(console.error);
    api.allocations().then(setAllocations).catch(console.error);
    api.navHistory().then(setNav).catch(console.error);
    api.factorSignals().then(setFactors).catch(console.error);
    api.riskMetrics().then(setRisk).catch(console.error);
    api.dataHealth().then(setHealth).catch(console.error);
    api.recentDecisions().then(setDecisions).catch(console.error);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0e17]">
      <TopBar summary={summary} health={health} />
      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: 2/3 */}
        <div className="lg:col-span-2 space-y-6">
          <AssetPie allocations={allocations} />
          <NavChart nav={nav} />
          <DecisionsCard decisions={decisions} />
        </div>
        {/* Right: 1/3 */}
        <div className="space-y-6">
          <RiskDash risk={risk} />
          <FactorHeatmap factors={factors} />
          <HealthCard health={health} />
        </div>
      </main>
    </div>
  );
}

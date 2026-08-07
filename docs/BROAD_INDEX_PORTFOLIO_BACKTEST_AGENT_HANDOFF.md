# Wealth OS — Broad Index Portfolio Backtest Agent Handoff

> **Document purpose**
>
> 本文档用于指导开发 Agent 实现 Wealth OS 的宽基基金组合（Broad Index Portfolio）正式回测体系。
>
> 本系统针对的是：
>
> - A股宽基
> - 港股宽基
> - 美股宽基
> - 黄金
> - 债券
> - 现金
> - BTC / Alternative
>
> 等长期资产配置组合。
>
> 目标不是验证某个短期交易信号，而是验证：
>
> > 在不同市场周期、不同投资起点、不同持续入金路径和现实交易约束下，一套长期资产配置规则是否能够稳定改善投资者的长期复利质量。

---

# 1. 回测核心原则

宽基组合回测必须与个股 Alpha 策略区分。

宽基 Core 的核心问题不是：

```text
能否预测明天涨跌
```

而是：

```text
能否在长期中：

维持合理收益
+
降低严重回撤
+
缩短恢复时间
+
提高不同起点下的稳定性
+
降低投资者路径风险
+
控制复杂度和执行成本
```

因此正式回测必须从“单次 CAGR 回测”升级为：

```text
Long-history Strategic Backtest
+
Real ETF Implementation Backtest
+
Investor Cash-flow Simulation
+
Robustness Validation
```

---

# 2. 三阶段回测架构

正式 Core Backtest 分为三个阶段。

---

## Stage A — Strategic Backtest

### 目标

验证资产配置思想是否跨周期成立。

### 数据

优先使用：

```text
Total Return Index
+
Gold Benchmark
+
Bond Total Return
+
Cash Rate
+
FX
```

例如：

```text
S&P 500 Total Return
Nasdaq-100 Total Return
CSI300 Total Return
HSI Total Return
Gold
Bond Total Return
Cash Yield
BTC（仅真实可投资时期）
USD/CNY
HKD/CNY
```

### 特点

- 尽可能长历史
- 15–30年优先
- 低交易摩擦假设
- 不绑定具体 ETF 产品
- 用于验证经济逻辑

### 回答的问题

```text
这个资产配置思想跨多个市场周期是否成立？
```

---

## Stage B — Implementation Backtest

### 目标

验证理论策略在真实可交易基金上是否可落地。

### 数据

使用真实 ETF：

```text
SPY / IVV / VOO
QQQ
510300
2800.HK
IAU / GLD
Bond ETF
```

### 必须加入

- ETF 上市日期
- 实际价格
- 总回报复权
- ETF 费用
- Tracking Error
- Bid-Ask Spread
- Commission
- Slippage
- FX Cost
- 真实交易日历
- 交易延迟

### 回答的问题

```text
理论策略在现实可交易产品上还能剩下多少收益？
```

---

## Stage C — Investor Simulation

### 目标

模拟真实个人投资者。

### 必须支持

```text
Initial Capital
+
Monthly Contribution
+
Cash Pool
+
FX Pool
+
Real Rebalancing
+
Transaction Costs
```

### 输出

```text
Final Wealth
Total Contribution
Investment Profit
TWR
XIRR
Drawdown
Recovery Time
```

### 回答的问题

```text
真实投资者在持续入金环境下的财富体验如何？
```

---

# 3. 双数据体系

系统必须同时维护：

```text
Strategic Asset Data
+
Tradable ETF Data
```

---

## 3.1 Strategic Asset Layer

代表风险暴露：

```text
US_LARGE_CAP
US_TECH
CN_LARGE_CAP
HK_LARGE_CAP
GOLD
BONDS
CASH
BTC
```

对应：

```text
Total Return Index
```

---

## 3.2 Tradable Instrument Layer

对应实际交易：

```text
SPY / IVV / VOO
QQQ
510300
2800.HK
GLD / IAU
Bond ETF
```

---

## 3.3 禁止事项

禁止：

```text
只因为某 ETF 上市晚，
就把所有资产的历史回测统一缩短到该日期。
```

正确做法：

```text
长期战略层：尽可能长
实际 ETF 层：按真实上市日期
```

分别报告。

---

# 4. Total Return 规则

股票宽基必须优先使用：

```text
Total Return
```

而不是：

```text
Price Return
```

---

## 4.1 总收益定义

```math
R_{total}
=
R_{price}
+
R_{dividend}
```

实际复合计算按现金分红和复权因子处理。

---

## 4.2 数据层必须保留

```text
raw_close
raw_open
raw_high
raw_low
dividend
split
adjustment_factor
total_return_index
```

不得只依赖供应商：

```text
Adj Close
```

---

# 5. 回测历史长度

## 5.1 推荐标准

```text
Preferred: 20Y+
Minimum:   10–15Y
```

## 5.2 必须覆盖

尽可能包括：

- 股票牛市
- 股票熊市
- 高通胀
- 低通胀
- 加息
- 降息
- 高波动
- 低波动
- 股票债券同跌
- 美股强、中国弱
- 中国强、美股弱

---

# 6. 多历史区间报告

不要只报告一个统一日期范围。

建议分别输出：

```text
Long Strategic Period
Full Multi-market Period
ETF Implementation Period
BTC-enabled Period
```

例如：

```text
Strategic:       2000–2026
Multi-market:    2005–2026
ETF Simulation:  2010–2026
BTC Enabled:     2014–2026
```

具体日期由数据可用性决定。

---

# 7. Multiple Starting Points

禁止只使用一个投资起点。

---

## 7.1 方法

每个月都可以作为一个新的初始投资日期：

```text
2006-01
2006-02
2006-03
...
```

对每个起点分别模拟。

---

## 7.2 持有周期

至少：

```text
3Y
5Y
10Y
```

---

## 7.3 输出

每个周期输出：

```text
Median CAGR
Mean CAGR
10th Percentile
25th Percentile
75th Percentile
90th Percentile
Worst
Best
Positive Return Ratio
Benchmark Win Rate
```

---

# 8. Rolling Return

至少计算：

```text
Rolling 1Y
Rolling 3Y
Rolling 5Y
Rolling 10Y
```

---

## 8.1 核心指标

```text
Median
Worst
10th Percentile
Positive Ratio
Benchmark Win Rate
```

---

# 9. Benchmark 体系

动态 Core 策略必须和强基准比较。

---

## B0 — Buy & Hold

```text
初始配置后不调仓
```

---

## B1 — Static SAA + Calendar Rebalance

例如：

```text
Annual Rebalance
```

---

## B2 — Static SAA + Drift Rebalance

最重要 Benchmark。

示例：

```text
当实际权重相对目标权重偏离超过阈值时才调仓。
```

---

## B3 — Risk-Matched Static Portfolio

若动态策略降低组合波动率：

```text
12% → 8%
```

必须构造一个接近 8% 波动率的静态组合比较。

目的：

避免将：

```text
少持有风险资产
```

误判为：

```text
动态策略产生 Alpha
```

---

# 10. 主要评价指标

宽基 Core 不应只看 Sharpe。

---

## 10.1 Return

- TWR
- CAGR
- Annualized Return
- XIRR
- Excess Return
- Final Wealth
- Investment Profit

---

## 10.2 Risk

- Annualized Volatility
- Downside Volatility
- VaR
- Expected Shortfall
- Beta

---

## 10.3 Drawdown

- Maximum Drawdown
- Average Drawdown
- Drawdown Duration
- Recovery Time
- Underwater Ratio
- Ulcer Index

---

## 10.4 Efficiency

- Sharpe
- Sortino
- Calmar
- Information Ratio

---

# 11. Core 重点指标

Core Strategy Report 必须重点展示：

```text
CAGR
Max Drawdown
Recovery Time
Calmar
Worst Rolling 3Y
Worst Rolling 5Y
Expected Shortfall
Underwater Ratio
Average Cash
Turnover
```

---

# 12. Wealth Experience Metrics

这是 Wealth OS 必须具备的特色指标。

---

## 12.1 Underwater Time

定义：

```text
组合净值低于历史高点的时间比例。
```

输出：

```text
Underwater Ratio
Longest Underwater Period
Median Underwater Duration
```

---

## 12.2 Recovery Distribution

针对超过阈值的回撤：

```text
>5%
>10%
>20%
```

分别统计：

```text
Average Recovery Time
Median Recovery Time
Maximum Recovery Time
```

---

## 12.3 Wealth Milestone Time

支持：

```text
100万 → 200万
200万 → 300万
300万 → 500万
```

或任意配置。

输出：

```text
Median Time
Best Time
Worst Time
```

---

# 13. Strategy NAV 与 Investor Return 分离

必须严格区分。

---

## 13.1 Strategy Return

使用：

```text
TWR
```

回答：

```text
策略本身的投资能力如何？
```

---

## 13.2 Investor Return

使用：

```text
XIRR
```

回答：

```text
在真实入金时间下，投资者资金的年化收益如何？
```

---

## 13.3 禁止事项

禁止将：

```text
新增资金
```

计入策略收益。

---

# 14. Regime Analysis

完整周期 CAGR 不足以评价宽基组合。

必须进行市场环境拆解。

---

## 14.1 市场 Regime

建议支持：

```text
Equity Bull
Equity Bear
Sideways

High Vol
Low Vol

Inflation Rising
Inflation Falling

Rates Rising
Rates Falling
```

---

## 14.2 Crisis Period

至少支持配置：

```text
2008 Global Financial Crisis
2011 Euro Crisis
2015 China Market Crash
2018 Q4 Selloff
2020 COVID Crash
2022 Inflation / Rate Shock
```

具体日期必须配置化。

---

## 14.3 Regime 输出

每个 Regime：

```text
Strategy Return
Benchmark Return
Excess Return
Volatility
Max Drawdown
Expected Shortfall
Average Cash
Turnover
```

---

# 15. Relative NAV

必须输出：

```math
RelativeNAV_t
=
NAV_{strategy,t} / NAV_{benchmark,t}
```

作用：

判断：

- 是否长期产生相对价值
- 是否只在危机期有效
- 是否长期牛市明显拖累
- 是否存在明显 Regime Dependency

---

# 16. FX Attribution

Wealth OS 默认总财富使用人民币计价。

海外资产收益必须拆解。

---

## 16.1 USD Asset

```math
R_{CNY}
=
(1+R_{USD})(1+R_{USDCNY})-1
```

近似：

```math
R_{CNY}
≈
R_{USD}
+
R_{FX}
```

---

## 16.2 输出

至少拆解：

```text
Local Asset Return
FX Return
Cross Term
Total CNY Return
```

---

## 16.3 Constant FX Backtest

必须支持：

```text
Constant FX Scenario
```

目的：

判断组合收益是否主要由某种货币长期升值贡献。

---

# 17. BTC 历史规则

禁止向 BTC 出现前回填虚拟 BTC 收益。

---

## 17.1 Pre-BTC Period

BTC 目标权重：

```text
归入 Cash
或
Alternative Placeholder
```

具体规则配置化。

---

## 17.2 BTC Available Period

只从：

```text
拥有可靠市场价格
且可合理投资
```

的时期启用。

---

## 17.3 必须对比

```text
With BTC
vs
Without BTC
```

---

# 18. Proxy Replacement Test

宽基资产拥有多个可替代产品，因此必须做代理替换验证。

---

## 18.1 示例

```text
SPY ↔ IVV ↔ VOO

GLD ↔ IAU

QQQ ↔ Nasdaq-100 Total Return

510300 ↔ CSI300 Total Return
```

---

## 18.2 验收逻辑

同一风险暴露换用合理代理后：

```text
核心策略结论不应发生方向性变化。
```

如果显著变化：

优先检查：

- 数据质量
- 复权
- ETF 上市时间
- 费用
- Tracking Error
- 交易规则
- 回测实现

---

# 19. Contribution Attribution

Adaptive Core 必须拆解模块贡献。

假设：

```text
SAA
+ Value
+ Trend
+ Risk Overlay
+ Cash
```

必须输出：

```text
Strategic Allocation Contribution
Value Contribution
Trend Contribution
Risk Overlay Contribution
Cash Drag / Benefit
FX Contribution
Trading Cost
```

---

## 19.1 使用目的

判断：

```text
哪些模块值得保留？
哪些模块只增加复杂度？
```

---

# 20. Ablation

必须测试：

```text
SAA

SAA + Value

SAA + Trend

SAA + Risk

SAA + Cash Overlay

SAA + Value + Trend

SAA + Trend + Risk

Full
```

若一个模块：

```text
收益下降
风险无改善
复杂度增加
交易增加
```

默认删除。

---

# 21. Parameter Robustness

禁止只展示最优参数。

必须测试参数邻域。

---

## 21.1 例子

Trend Lookback：

```text
180
200
220
240
260
280
300
```

---

## 21.2 目标

希望看到：

```text
Plateau
```

而不是：

```text
Sharp Peak
```

---

# 22. Transaction Cost Stress

至少测试：

```text
1× Cost
2× Cost
3× Cost
```

包含：

- Commission
- Spread
- Slippage
- FX Cost
- ETF Fee

---

# 23. Signal Delay Stress

至少测试：

```text
0 Day
1 Day
3 Days
5 Days
```

若 1–3 天延迟后策略显著失效：

必须检查：

- 是否存在未来数据
- 信号是否过度精确
- 回测成交假设是否不现实

---

# 24. Data Stress Test

支持：

- Missing Day
- Price Noise
- Alternative Provider
- Alternative Adjustment
- FX Delay
- Different Calendar
- ETF Proxy Replacement

---

# 25. Block Bootstrap

宽基回报存在序列相关性。

优先使用：

```text
Block Bootstrap
```

而不是单纯 IID Bootstrap。

---

## 25.1 输出

```text
CAGR Distribution
Sharpe Distribution
MaxDD Distribution
Calmar Distribution
Probability of Underperforming Benchmark
Probability of Negative Rolling 3Y
```

---

# 26. 最终结果必须输出分布

禁止只报告：

```text
CAGR = 8.37%
```

应报告：

```text
10Y Rolling CAGR

Median
Mean
25th Percentile
10th Percentile
Worst
Best
```

---

# 27. Probability Metrics

最终报告建议输出：

```text
P(5Y Return < 0)
P(10Y CAGR < threshold)
P(MaxDD > threshold)
P(Underperform Static SAA over 5Y)
P(Underperform Static SAA over 10Y)
```

---

# 28. 推荐正式 Pipeline

```text
                    DATA
                      │
        ┌─────────────┴─────────────┐
        │                           │
Total Return Index              Real ETF
Long History                   Real Execution
        │                           │
        ▼                           ▼
Strategic Backtest        Implementation Backtest
        │                           │
        └─────────────┬─────────────┘
                      ▼
                Strategy Engine
                      │
                      ▼
              Multiple Start Dates
                      │
                      ▼
               Rolling Windows
                      │
                      ▼
                Regime Analysis
                      │
                      ▼
                Ablation Test
                      │
                      ▼
              Parameter Surface
                      │
                      ▼
               Cost / Delay Stress
                      │
                      ▼
             Proxy Replacement
                      │
                      ▼
              Block Bootstrap
                      │
                      ▼
             Investor Cash Flows
                      │
                      ▼
               Strategy Report
```

---

# 29. 推荐代码模块

```text
src/wealth_os/
├── backtest/
│   ├── strategic.py
│   ├── implementation.py
│   ├── investor.py
│   ├── total_return.py
│   ├── cashflow.py
│   └── fx.py
│
├── evaluation/
│   ├── benchmarks.py
│   ├── rolling.py
│   ├── starting_points.py
│   ├── regime.py
│   ├── relative_nav.py
│   ├── attribution.py
│   ├── ablation.py
│   ├── parameter_surface.py
│   ├── proxy_test.py
│   ├── cost_stress.py
│   ├── delay_stress.py
│   ├── data_stress.py
│   ├── bootstrap.py
│   └── report.py
│
└── domain/
    ├── strategic_asset.py
    ├── tradable_instrument.py
    ├── benchmark.py
    └── backtest_result.py
```

---

# 30. 推荐领域对象

```python
StrategicAsset
TradableInstrument
AssetProxy
BenchmarkDefinition
BacktestPeriod
StrategicBacktestResult
ImplementationBacktestResult
InvestorSimulationResult
RollingReturnResult
StartingPointResult
RegimeResult
FXAttributionResult
ModuleAttributionResult
StressTestResult
BootstrapResult
BroadIndexStrategyReport
```

---

# 31. Agent 第一阶段开发任务

## Sprint 1 — Backtest Domain

- [ ] StrategicAsset
- [ ] TradableInstrument
- [ ] AssetProxy
- [ ] BenchmarkDefinition
- [ ] 三类 Backtest Result

## Sprint 2 — Total Return

- [ ] Price Return
- [ ] Dividend Return
- [ ] Total Return
- [ ] ETF Adjusted Return
- [ ] 数据口径校验

## Sprint 3 — Three-stage Backtest

- [ ] Strategic Backtest
- [ ] Implementation Backtest
- [ ] Investor Simulation

## Sprint 4 — Benchmarks

- [ ] Buy & Hold
- [ ] Static SAA Annual
- [ ] Static SAA Drift
- [ ] Risk-matched SAA

## Sprint 5 — Distribution Evaluation

- [ ] Multiple Starting Points
- [ ] Rolling 1Y/3Y/5Y/10Y
- [ ] Outcome Distribution
- [ ] Benchmark Win Rate

## Sprint 6 — Regime & Crisis

- [ ] Regime Config
- [ ] Crisis Period Config
- [ ] Regime Report

## Sprint 7 — FX

- [ ] CNY Return Attribution
- [ ] Constant FX Scenario
- [ ] FX Cost

## Sprint 8 — Robustness

- [ ] Proxy Replacement
- [ ] Parameter Surface
- [ ] Cost Stress
- [ ] Delay Stress
- [ ] Data Stress

## Sprint 9 — Bootstrap

- [ ] Block Bootstrap
- [ ] CAGR Distribution
- [ ] MaxDD Distribution
- [ ] Underperformance Probability

## Sprint 10 — Final Report

- [ ] Strategic Result
- [ ] Implementation Result
- [ ] Investor Result
- [ ] Distribution Summary
- [ ] Regime Summary
- [ ] Robustness Summary
- [ ] Recommendation

---

# 32. CLI 建议

```bash
wealth-os backtest strategic \
  --strategy adaptive_core

wealth-os backtest implementation \
  --strategy adaptive_core

wealth-os backtest investor \
  --strategy adaptive_core \
  --monthly-contribution 50000

wealth-os backtest starting-points \
  --strategy adaptive_core

wealth-os backtest rolling \
  --strategy adaptive_core \
  --windows 1y,3y,5y,10y

wealth-os backtest regimes \
  --strategy adaptive_core

wealth-os backtest proxy-test \
  --strategy adaptive_core

wealth-os backtest stress \
  --strategy adaptive_core \
  --cost-multiplier 2

wealth-os backtest report \
  --strategy adaptive_core
```

---

# 33. 第一版正式验收标准

一个宽基 Core Strategy 至少满足以下条件，才值得进入下一阶段：

- [ ] 长期战略回测 >= 15 年，若数据不足需明确说明
- [ ] 使用 Total Return 口径
- [ ] 实际 ETF 回测独立完成
- [ ] 真实持续入金模拟完成
- [ ] 至少三个强 Benchmark
- [ ] 多起点结果稳定
- [ ] Worst Rolling 3Y/5Y 可解释
- [ ] MaxDD 或 Recovery Time 有明显改善
- [ ] 结论不依赖单一历史阶段
- [ ] 参数附近形成 Plateau
- [ ] ETF Proxy 替换后结论不变
- [ ] Cost ×2 后核心结论仍成立
- [ ] Signal Delay 1–3 天后核心结论仍成立
- [ ] OOS 仍保持核心结论
- [ ] FX Contribution 已独立归因
- [ ] BTC 不做历史回填
- [ ] TWR 和 XIRR 已分离
- [ ] 最终报告输出概率分布，不只输出单点 CAGR

---

# 34. 最小“好策略”判断标准

对于 Broad Index Core：

```text
1. 长期收益不明显差于 Static SAA
2. Max Drawdown 或 Recovery Time 至少显著改善一个
3. Worst Rolling 3Y / 5Y 改善
4. 多起点下结论稳定
5. 参数邻域稳定
6. 代理资产替换稳定
7. 成本和延迟压力下稳定
8. 不依赖单一宏观时期
9. OOS 结果成立
10. 复杂策略必须显著优于简单策略
```

---

# 35. 复杂度原则

如果：

```text
Adaptive Core
```

没有明显优于：

```text
Risk Managed Core
```

则删除 Value / Trend 等额外复杂模块。

如果：

```text
Risk Managed Core
```

没有明显优于：

```text
Static SAA + Drift Rebalance
```

则优先使用简单静态配置。

原则：

```text
Simple > Complex
Robust > Optimal
Distribution > Single Point
OOS > IS
Risk-adjusted > Raw Return
Realistic > Idealized
```

---

# 36. 最终目标

本回测体系最终需要回答：

> 对一个长期持有宽基基金、持续投入资金、以人民币衡量财富的真实投资者而言，这个组合策略是否能在不同历史起点和不同市场环境下，以合理的收益代价换取更好的回撤、恢复时间、长期复利稳定性和投资体验？

这才是 Wealth OS 对 Broad Index Core Strategy 的正式回测标准。

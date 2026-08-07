# Wealth OS — Core Strategy Research & Validation Protocol

> **Document purpose**
>
> 本文档用于指导开发 Agent 实现 Wealth OS 的 Core Strategy Research / Validation 体系。
>
> 目标不是“找到历史收益最高的策略”，而是建立一套统一、可复现、可审计的研究流程，用于判断一个候选策略是否：
>
> - 有明确经济逻辑
> - 在不同市场环境下稳定
> - 不依赖单一参数点
> - 不依赖单一历史时期
> - 对交易成本和执行延迟鲁棒
> - 没有明显数据泄漏与过拟合
> - 相比简单基准真正改善风险收益结构
> - 有资格进入 Shadow / Paper / Live 阶段

---

# 1. Core Strategy 的根本目标

Wealth OS 的 Core 不以最大化历史 CAGR 为唯一目标。

其优化目标应理解为：

```text
在满足长期收益要求的前提下：

最大化长期复利质量
+
降低尾部风险
+
降低路径风险
+
降低行为风险
+
控制复杂度和交易成本
```

Core 策略的主要职责：

- 提供长期风险资产暴露
- 控制严重回撤
- 维持跨市场和跨币种分散
- 在高风险时期减少风险预算
- 在持续入金环境中稳定配置资本
- 避免因为择时错误造成永久资本损失

Core 不应该承担：

- 高频 Alpha
- 精确预测顶部和底部
- 个股级超额收益
- 高频择时
- 复杂黑盒交易

---

# 2. 候选 Core 策略架构

第一阶段只研究三类 Candidate。

不要一次同时研究大量策略。

## 2.1 Candidate A — Static SAA

基准策略：

```text
Strategic Asset Allocation
+
Drift-based Rebalancing
```

作用：

- 作为强基准
- 衡量所有动态模块是否真正创造价值

战略权重不能通过全样本回测直接最优化。

战略配置应主要来自：

- 长期风险预算
- 资产长期风险溢价
- 地域分散
- 币种分散
- 最大可接受回撤
- 流动性需求

## 2.2 Candidate B — Risk Managed Core

```text
Static SAA
+
Portfolio Volatility Targeting
+
Drawdown Governor
```

Candidate B 只回答一个问题：

> 是否能够在不显著牺牲长期收益的情况下改善尾部风险和回撤路径？

## 2.3 Candidate C — Adaptive Core

```text
Static SAA
+
Slow Value / Expected Return Tilt
+
Trend State
+
Portfolio Volatility Targeting
+
Drawdown Governor
```

Candidate C 需要证明：

```text
Value / Trend
```

相对 Candidate B 的额外复杂度是值得的。

如果没有显著增量价值，应该优先保留 Candidate B。

如果 Candidate B 也没有明显优于 Candidate A，则优先选择 Candidate A。

---

# 3. 推荐的分层策略架构

禁止继续使用简单的：

```text
Value × Trend × Risk → Weight
```

推荐使用职责分离的控制体系：

```text
Strategic Allocation
        ↓
Expected Return / Value Tilt
        ↓
Trend Defense
        ↓
Portfolio Risk Targeting
        ↓
Drawdown Governor
        ↓
Portfolio Constraints
        ↓
Cash Residual
        ↓
Execution & Rebalancing
```

---

# 4. Strategic Allocation Layer

## 4.1 职责

决定长期配置中枢。

## 4.2 设计原则

- 不依赖短期信号
- 不通过单次回测直接优化
- 变更频率极低
- 所有动态策略都围绕 SAA 小幅调整

## 4.3 输出

```python
StrategicWeights
```

示例：

```yaml
SP500: 0.25
CSI300: 0.20
HSI: 0.10
GOLD: 0.10
BOND: 0.20
CASH: 0.13
BTC: 0.02
```

以上仅为结构示例，不代表正式目标权重。

---

# 5. Value / Expected Return Layer

## 5.1 职责

Value 不用于短期择时。

其职责是：

> 根据长期预期收益，对战略配置进行缓慢、有限的偏移。

## 5.2 基础形式

```math
w_i^{value} = w_i^{SAA}(1+\alpha_v V_i)
```

其中：

```text
V_i ∈ [-1, 1]
```

`alpha_v` 必须受到严格限制。

## 5.3 建议行为

例如战略权重为 25%：

```text
极度低估 → 30%
正常     → 25%
极度高估 → 20%
```

而不是：

```text
0% ↔ 50%
```

## 5.4 更新频率

推荐：

- 月度
- 季度

不推荐日频更新。

## 5.5 长期演进方向

Value Score 最终应升级为 Expected Return Model：

```math
E[R] \approx DividendYield + FundamentalGrowth + ValuationMeanReversion + FXContribution
```

---

# 6. Trend Defense Layer

## 6.1 职责

Trend 的主要目标不是增加短期 Alpha，而是降低持续熊市和趋势性下跌风险。

## 6.2 第一版建议

保持简单：

```text
12M Momentum
+
200D Moving Average
```

不要一开始加入大量技术指标。

## 6.3 状态机

建议将 Trend 转化为离散状态：

```text
BULL
NEUTRAL
BEAR
```

示例：

```text
BULL     risk exposure = 100%
NEUTRAL  risk exposure = 80%
BEAR     risk exposure = 50~60%
```

具体参数必须通过研究协议验证，以上仅为起始研究范围。

## 6.4 Hysteresis

进入和退出状态必须使用不同阈值。

目的：

- 减少状态反复切换
- 减少交易
- 降低参数敏感性

---

# 7. Portfolio Volatility Targeting Layer

## 7.1 职责

Risk Layer 应控制整个组合风险，而不是让每个资产独立做 Risk Scaling。

## 7.2 组合预测波动率

```math
\sigma_p = \sqrt{w^T \Sigma w}
```

## 7.3 风险缩放

```math
k = \min\left(1, \frac{\sigma_{target}}{\sigma_p}\right)
```

最终：

```math
w_{risk} = k \cdot w
```

未使用风险预算进入 Cash。

因此：

> Cash 是未使用的风险预算，而不是独立择时信号。

## 7.4 要求

- 波动率估计必须 Point-in-Time
- 需要平滑
- 禁止根据未来实现波动率调仓
- 需要限制单日风险暴露变化
- 必须测试不同估计窗口

---

# 8. Drawdown Governor

## 8.1 职责

Volatility Targeting 不能完全替代 Drawdown Control。

Drawdown Governor 用于处理：

- 极端市场
- 风险模型失效
- 资产相关性突然上升
- 长期资本路径保护

## 8.2 状态机

推荐：

```text
NORMAL
CAUTION
DEFENSIVE
CRISIS
```

研究初始值可以从：

```text
DD < -8%   → CAUTION
DD < -12%  → DEFENSIVE
DD < -18%  → CRISIS
```

开始。

这些阈值不是最终参数。

## 8.3 风险预算示例

```text
NORMAL       100%
CAUTION       85%
DEFENSIVE     65%
CRISIS        45%
```

## 8.4 恢复机制

必须：

```text
Fast De-risk
Slow Re-risk
```

并设置 hysteresis，避免状态反复切换。

---

# 9. Execution & Rebalancing Layer

## 9.1 原则

```text
Signal ≠ Trade
```

信号变化不应该自动产生交易。

## 9.2 建议研究初始范围

```text
目标权重变化 < 2%
→ 不交易

实际权重漂移 < 3%
→ 不交易

距离上次主动调仓 < 20 个交易日
→ 默认不主动调仓

存在新增资金
→ 优先使用新增资金修复低配
```

## 9.3 必须考虑

- commission
- tax
- bid-ask spread
- slippage
- FX cost
- minimum order
- cooldown
- minimum trade size

---

# 10. Strategy Evaluation Engine

应实现独立模块：

```text
Strategy Evaluation Engine
```

禁止 Strategy 自己决定自己是否优秀。

输入：

```python
strategy
benchmark
experiment_registry
data_version
evaluation_config
```


输出：

```text
StrategyReport
```

---

# 11. Strategy Report 结构

```text
Strategy Report
│
├── Metadata
├── Performance
├── Risk
├── Drawdown
├── Rolling Returns
├── Benchmark Comparison
├── Regime Analysis
├── Attribution
├── Ablation
├── Parameter Surface
├── Walk Forward
├── Out-of-Sample
├── Cost Stress
├── Delay Stress
├── Data Stress
├── Bootstrap
├── PBO
├── Deflated Sharpe Ratio
├── Complexity Assessment
├── Gate Results
└── Recommendation
```

---

# 12. Benchmark Gate

任何 Candidate 都必须和以下基准比较。

## B0 Buy & Hold

```text
资产初始配置后不调仓
```

## B1 Static SAA + Calendar Rebalance

例如年度再平衡。

## B2 Static SAA + Drift Rebalance

例如权重漂移超过阈值后再平衡。

这是最重要的基准。

## B3 Risk-matched Benchmark

如果策略波动率明显较低，必须构造风险水平相近的静态组合。

禁止只比较“低风险动态策略 vs 高风险静态策略”的 Sharpe。

---

# 13. Performance Metrics

至少输出：

## Return

- TWR
- CAGR
- Annualized Return
- XIRR
- Excess Return

## Risk

- Annualized Volatility
- Downside Volatility
- VaR
- Expected Shortfall
- Beta

## Drawdown

- Maximum Drawdown
- Average Drawdown
- Drawdown Duration
- Recovery Time
- Ulcer Index

## Efficiency

- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Information Ratio

## Relative

- Tracking Error
- Relative NAV
- Excess Return
- Relative Drawdown

## Execution

- Turnover
- Order Count
- Trading Cost
- FX Cost
- Average Cash
- Maximum Cash
- Average Risk Exposure

---

# 14. Core 特别关注指标

Core 策略不能只看 Sharpe。

必须重点输出：

```text
CAGR
Max Drawdown
Calmar
Expected Shortfall
Worst Rolling 1Y
Worst Rolling 3Y
Worst Rolling 5Y
Recovery Time
Average Cash
Turnover
```

对 Core：

> Calmar、Worst Rolling 3Y 和 Recovery Time 往往比单纯 Sharpe 更重要。

---

# 15. Relative NAV

必须生成：

```math
RelativeNAV_t = \frac{NAV_{strategy,t}}{NAV_{benchmark,t}}
```

用于判断：

- 策略是否长期持续创造相对价值
- 是否只在危机时改善
- 是否在牛市长期拖累
- 是否存在 regime dependency

---

# 16. Regime Analysis

禁止只报告一个全周期 CAGR。

至少需要拆解：

```text
Bull
Bear
Sideways
High Vol
Low Vol
Inflation Rising
Inflation Falling
Rates Rising
Rates Falling
```

并单独分析主要危机阶段，例如：

```text
2008 Global Financial Crisis
2011 Euro Crisis
2015 China Market Crash
2018 Q4 Selloff
2020 COVID Crash
2022 Inflation / Rate Shock
```

实际日期区间必须在系统配置中明确，不应硬编码在 Strategy 中。

---

# 17. Regime Report

每个 Regime 输出：

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

最终回答：

> 策略到底在哪些市场环境下创造价值？

---

# 18. Ablation Test

完整策略假设：

```text
SAA
+ Value
+ Trend
+ VolTarget
+ Drawdown
```

必须至少运行：

```text
A0: SAA
A1: SAA + Value
A2: SAA + Trend
A3: SAA + VolTarget
A4: SAA + Drawdown
A5: SAA + Trend + VolTarget
A6: SAA + Value + Trend
A7: SAA + VolTarget + Drawdown
A8: Full Strategy
```

输出每个模块的边际贡献：

```text
ΔCAGR
ΔMaxDD
ΔCalmar
ΔTurnover
ΔCost
```

如果模块：

```text
收益下降
风险没有改善
复杂度增加
交易增加
```

默认应删除。

---

# 19. Parameter Surface Test

禁止只展示最优参数。

必须评估参数邻域。

例如 Momentum Lookback：

```text
180
200
220
240
260
280
300
```

好策略期望形成宽平台 Plateau，而不是尖峰 Peak。

---

# 20. Parameter Robustness Score

建议实现：

```text
Parameter Robustness Score
```

定义：

```text
在预定义参数邻域中，
满足策略方向和核心 Gate 的参数比例。
```

初始验收建议：

```text
>= 80%
```

参数邻域应在实验开始前定义。

---

# 21. In-Sample / Out-of-Sample Protocol

## 21.1 禁止事项

禁止：

```text
在全历史数据上反复调参数
然后把同一段历史作为最终验证结果
```

## 21.2 推荐阶段

```text
Research Period
Validation Period
Out-of-Sample Period
```

最终策略评级必须主要基于 OOS，而不是 In-Sample。

---

# 22. Walk-Forward Validation

必须实现 Walk-Forward：

```text
Train / Calibrate
        ↓
Next Period Test
        ↓
Roll Forward
        ↓
Repeat
```

例如：

```text
5Y Research
→ 1Y OOS
→ 向前滚动
```

实际窗口应由配置定义。

禁止针对结果事后选择最佳窗口。

---

# 23. Multiple Starting Point Test

对于持续入金投资者，需要测试不同开始时间。

例如每个月作为一个新的初始投资日期。

输出：

- CAGR distribution
- XIRR distribution
- Max Drawdown distribution
- Worst outcome
- Median outcome
- 10th percentile
- 90th percentile

避免策略效果只依赖某一个幸运起点。

---

# 24. Rolling Return Test

至少计算：

```text
Rolling 1Y
Rolling 3Y
Rolling 5Y
Rolling 10Y
```

重点指标：

```text
Median
10th Percentile
Worst
Positive Ratio
Benchmark Win Rate
```

---

# 25. Cost Stress Test

必须测试：

```text
Base Cost
2 × Cost
3 × Cost
```

至少包括：

- commission
- spread
- slippage
- FX cost

策略如果在成本翻倍后完全失效，应降低评级。

---

# 26. Signal Delay Stress Test

必须测试：

```text
0 day
1 day
3 days
5 days
```

如果延迟 1–3 天策略立即崩溃，通常说明：

- 信号过于精确
- 存在数据时间语义问题
- 可能有未来信息泄漏
- 实盘可执行性差

---

# 27. Data Perturbation Test

需要测试：

- 少量价格噪声
- 缺失交易日
- 使用备用数据源
- 不同复权数据
- 数据延迟
- FX 延迟
- 基准收益替代
- ETF Proxy Replacement

例如：

```text
SPY ↔ IVV ↔ VOO
GLD ↔ IAU
```

策略不应因为同类资产代理变化而完全失效。

---

# 28. Bootstrap / Monte Carlo

目标不是预测未来价格。

目标是评估历史结果的统计不确定性。

至少输出：

- CAGR confidence interval
- Sharpe confidence interval
- Max Drawdown distribution
- Probability of underperforming benchmark
- Probability of negative rolling 3Y outcome

需要优先支持：

```text
Block Bootstrap
```

而不是简单 IID Bootstrap。

---

# 29. Backtest Overfitting Governance

从现在开始必须保存全部实验。

失败实验也必须保存。

禁止只保存最佳结果。

---

# 30. Experiment Registry

每次实验记录：

```text
experiment_id
strategy_id
strategy_version
code_version
data_version
benchmark_id
parameter_space
selected_parameters
research_period
validation_period
oos_period
created_at
author_or_agent
hypothesis
result
gate_status
notes
```

---

# 31. Multiple Testing

必须记录：

```text
同一研究方向一共尝试过多少 Candidate
多少参数组合
多少信号定义
多少资产替代方案
```

最终策略评级必须考虑 Multiple Testing。

---

# 32. Probability of Backtest Overfitting

建议实现：

```text
PBO
Probability of Backtest Overfitting
```

用于衡量：

> 从大量候选策略中选出的“最佳策略”在样本外失效的概率。

PBO 应属于 Validation OS，而非 Strategy Module。

---

# 33. Deflated Sharpe Ratio

实现：

```text
Deflated Sharpe Ratio
```

用于修正：

- Multiple Testing
- Selection Bias
- Non-normal Return Distribution

禁止只展示 Raw Sharpe。

---

# 34. Complexity Penalty

复杂策略应承担额外证明责任。

建议记录：

```text
number_of_parameters
number_of_signals
number_of_states
number_of_thresholds
annual_turnover
dependency_count
```

定义 Complexity Score。

同等 OOS 表现下：

```text
更简单的策略优先
```

---

# 35. Strategy Validation Gates

策略必须逐 Gate 验证。

## Gate 1 — Correctness

必须通过：

- 数据校验
- Point-in-Time
- 无未来信息
- 会计恒等式
- 权重约束
- 双引擎对账

失败：

```text
REJECTED
```

## Gate 2 — Return

Core 不要求显著跑赢。

初始研究标准可以设置：

```text
OOS CAGR >= Static SAA CAGR - 0.5% ~ 1.0%
```

具体阈值必须配置化。

## Gate 3 — Drawdown

至少满足一个显著改善条件。

例如研究初始目标：

```text
Max Drawdown 相对下降 >= 20%
```

或者 Expected Shortfall 明显改善。

## Gate 4 — Risk-adjusted Efficiency

至少一项显著改善：

```text
Calmar
Sortino
Expected Shortfall-adjusted Return
```

例如：

```text
Calmar improvement >= 15% ~ 20%
```

仅作为初始研究阈值。

## Gate 5 — Robustness

建议：

```text
>= 80% 参数邻域保持相同结论方向
```

## Gate 6 — Regime Robustness

不能全部超额收益来自一个孤立历史阶段。

## Gate 7 — Cost Robustness

```text
2 × transaction cost
```

后策略核心结论仍需成立。

## Gate 8 — Delay Robustness

```text
1~3 day delay
```

不能导致策略完全失效。

## Gate 9 — OOS

OOS 必须满足最核心的：

- Return Gate
- Drawdown Gate
- Risk-adjusted Gate

否则不得晋级。

## Gate 10 — Overfitting

需要输出：

```text
PBO
Deflated Sharpe
Experiment Count
Complexity Score
```

若过拟合风险过高，不得进入 Shadow。

---

# 36. Strategy Status Machine

```text
REJECTED
    ↓
RESEARCH
    ↓
CANDIDATE
    ↓
VALIDATED
    ↓
SHADOW
    ↓
PAPER
    ↓
LIVE
```

---

# 37. 状态定义

## RESEARCH

满足：

- 有明确经济假设
- 代码可运行
- 尚未通过正式验证

## CANDIDATE

满足：

- 基础回测可行
- 初步优于基准
- 已完成基本 Ablation
- 已完成参数表面测试

## VALIDATED

满足：

- OOS 通过
- Walk-forward 通过
- Cost / Delay Stress 通过
- 参数鲁棒
- 过拟合风险可接受

## SHADOW

只生成真实每日目标仓位，不实际交易，并与理论回测进行实时偏差分析。

## PAPER

模拟真实：

- 订单
- 滑点
- 成本
- 交易时间
- 调仓规则

## LIVE

只有在：

```text
VALIDATED
→ SHADOW
→ PAPER
```

均通过后才能进入。

---

# 38. Promotion Rules

任何升级必须由 Validation Engine 决定。

Strategy 不得自行升级状态。

示例：

```python
class StrategyPromotionPolicy(Protocol):
    def evaluate(
        self,
        report: StrategyReport,
    ) -> StrategyStatus:
        ...
```

---

# 39. 推荐领域对象

```python
StrategyDefinition
StrategyRun
BenchmarkDefinition
ExperimentDefinition
ExperimentResult
EvaluationConfig
PerformanceMetrics
RiskMetrics
RegimeResult
AblationResult
ParameterSurfaceResult
StressTestResult
BootstrapResult
OverfittingMetrics
StrategyGateResult
StrategyReport
StrategyStatus
```

---

# 40. Strategy Interface

建议统一：

```python
class Strategy(Protocol):
    def generate_target(
        self,
        context: StrategyContext,
    ) -> TargetPortfolio:
        ...
```

Strategy 只负责：

```text
输入市场状态
→ 输出目标组合
```

不得：

- 自己计算最终评分
- 自己决定是否优秀
- 自己选择 Benchmark
- 自己修改历史数据

---

# 41. Evaluation Engine Interface

```python
class StrategyEvaluator(Protocol):
    def evaluate(
        self,
        strategy: StrategyDefinition,
        benchmarks: list[BenchmarkDefinition],
        config: EvaluationConfig,
    ) -> StrategyReport:
        ...
```

---

# 42. 推荐模块目录

```text
src/wealth_os/
├── strategy/
│   ├── core/
│   │   ├── static_saa.py
│   │   ├── risk_managed.py
│   │   └── adaptive_core.py
│   └── protocol.py
│
├── evaluation/
│   ├── engine.py
│   ├── benchmarks.py
│   ├── performance.py
│   ├── risk.py
│   ├── drawdown.py
│   ├── rolling.py
│   ├── regime.py
│   ├── attribution.py
│   ├── ablation.py
│   ├── parameter_surface.py
│   ├── walk_forward.py
│   ├── stress_cost.py
│   ├── stress_delay.py
│   ├── stress_data.py
│   ├── bootstrap.py
│   ├── pbo.py
│   ├── deflated_sharpe.py
│   ├── complexity.py
│   ├── gates.py
│   └── report.py
│
├── experiments/
│   ├── registry.py
│   ├── repository.py
│   └── models.py
│
└── governance/
    ├── promotion.py
    └── strategy_status.py
```

---

# 43. CLI 建议

```bash
wealth-os strategy run \
  --strategy adaptive_core \
  --config configs/strategies/adaptive_core.yaml

wealth-os strategy compare \
  --strategy adaptive_core \
  --benchmark static_saa

wealth-os strategy ablation \
  --strategy adaptive_core

wealth-os strategy parameter-surface \
  --strategy adaptive_core

wealth-os strategy walk-forward \
  --strategy adaptive_core

wealth-os strategy stress \
  --strategy adaptive_core \
  --type cost

wealth-os strategy validate \
  --strategy adaptive_core

wealth-os strategy report \
  --strategy adaptive_core

wealth-os strategy promote \
  --strategy adaptive_core
```

---

# 44. 配置建议

```yaml
evaluation:
  benchmarks:
    - buy_and_hold
    - static_saa_calendar
    - static_saa_drift
    - risk_matched_saa

  rolling_windows:
    - 252
    - 756
    - 1260
    - 2520

  cost_multipliers:
    - 1.0
    - 2.0
    - 3.0

  delay_days:
    - 0
    - 1
    - 3
    - 5

  parameter_robustness_threshold: 0.80

  core_return_tolerance:
    annualized_return_gap: 0.01

  target_drawdown_improvement: 0.20
  target_calmar_improvement: 0.15
```

以上阈值都必须配置化，不能硬编码。

---

# 45. 第一阶段 Agent 开发任务

## Sprint 1 — Evaluation Domain

- [ ] 定义 StrategyReport
- [ ] 定义所有 Metrics DTO
- [ ] 定义 Benchmark
- [ ] 定义 Gate
- [ ] 定义 StrategyStatus
- [ ] 定义 Experiment Registry

## Sprint 2 — Benchmark & Metrics

- [ ] Buy & Hold
- [ ] Static SAA Calendar
- [ ] Static SAA Drift
- [ ] Risk-matched Benchmark
- [ ] Performance Metrics
- [ ] Drawdown Metrics
- [ ] Rolling Metrics
- [ ] Relative NAV

## Sprint 3 — Ablation & Parameter Surface

- [ ] Ablation Runner
- [ ] Parameter Grid Runner
- [ ] Parameter Surface
- [ ] Robustness Score

## Sprint 4 — OOS

- [ ] Train / Validation / OOS Split
- [ ] Walk-forward
- [ ] Multiple Starting Points
- [ ] Rolling Outcomes

## Sprint 5 — Stress Tests

- [ ] Cost Stress
- [ ] Signal Delay
- [ ] Data Perturbation
- [ ] Proxy Replacement

## Sprint 6 — Statistical Validation

- [ ] Block Bootstrap
- [ ] Confidence Interval
- [ ] PBO
- [ ] Deflated Sharpe
- [ ] Complexity Score

## Sprint 7 — Governance

- [ ] Gate Engine
- [ ] Strategy Status
- [ ] Promotion Policy
- [ ] Audit Log

## Sprint 8 — Candidate Strategies

- [ ] Static SAA
- [ ] Risk Managed Core
- [ ] Adaptive Core

---

# 46. 第一阶段验收标准

Evaluation Engine 第一版必须能够：

- [ ] 对一个 Strategy 自动跑完整回测
- [ ] 自动生成多个 Benchmark
- [ ] 输出 CAGR / TWR / XIRR
- [ ] 输出 MaxDD / Recovery / ES
- [ ] 输出 Calmar / Sortino / Sharpe
- [ ] 输出 Relative NAV
- [ ] 输出 Rolling 1Y / 3Y / 5Y
- [ ] 输出 Regime Analysis
- [ ] 自动 Ablation
- [ ] 自动 Parameter Surface
- [ ] 自动 Walk-forward
- [ ] 自动 Cost Stress
- [ ] 自动 Signal Delay
- [ ] 自动 Bootstrap
- [ ] 记录 Experiment Count
- [ ] 输出 PBO
- [ ] 输出 Deflated Sharpe
- [ ] 输出 Gate Result
- [ ] 输出最终 Strategy Status

---

# 47. Research Discipline

Agent 必须遵守：

1. 先定义 Hypothesis，再跑实验。
2. 参数范围在看到结果前确定。
3. 所有实验都写入 Registry。
4. 失败实验不得删除。
5. 禁止只展示最优参数。
6. 禁止根据 OOS 结果继续反复调同一策略后仍称其为 OOS。
7. 任何修改后重新使用过的 OOS 数据必须降级为 Validation Data。
8. 最终必须保留新的未使用数据或进入 Forward / Shadow 验证。
9. 复杂策略必须显著优于简单策略才允许保留。
10. 所有结果必须记录 `data_version` 和 `code_version`。

---

# 48. Decision Principle

策略选择遵循：

```text
Simple > Complex
Robust > Optimal
OOS > IS
Risk-adjusted > Raw Return
Repeatable > Lucky
Explainable > Black-box
```

---

# 49. 最终决策逻辑

如果：

```text
Adaptive Core
```

没有明显优于：

```text
Risk Managed Core
```

则使用 Risk Managed Core。

如果：

```text
Risk Managed Core
```

没有明显优于：

```text
Static SAA
```

则使用 Static SAA。

这是本体系最重要的原则：

> **复杂度本身不是价值。**

策略只有在可以证明增加复杂度带来稳定、可复现的风险收益改善时，才应该被加入系统。

---

# 50. 最终目标

Strategy Validation System 最终要回答的不是：

> 哪个策略历史收益最高？

而是：

> 在给定风险预算和现实执行约束下，哪一个策略最有可能以最低的模型风险、过拟合风险和行为风险，长期稳定地帮助投资者实现财富复利？

这才是 Wealth OS 对 Core Strategy 的最终评价标准。

# 06. Portfolio & Capital OS 设计

## 1. 核心职责

Portfolio OS 决定“资产之间如何配置”；Capital Manager 决定“当前总资本有多少投入风险资产、多少保留现金，以及 Core 和 Satellite 如何分配资金”。两者共享约束，但职责分离。

## 2. 一级账户结构

```text
Total Investable Capital =
  Core + Satellite + Alternative + Cash
```

全部资金均为长期可投资资金，生活资金不进入本系统。

### 默认战略锚

- Core：约 75%–80%；
- Satellite：约 15%–20%；
- Alternative：约 1%–3%；
- Cash：动态。

锚点不是硬编码，具体由配置和风险档位管理。

## 3. 现金模型

现金至少按币种区分：

- CNY Cash；
- USD Cash；
- HKD Cash，可选。

每个现金资产有：

- 收益序列；
- 目标和上下限；
- 可用于哪些市场的交易；
- 换汇成本；
- 流动性等级。

降低某个指数仓位不必增加其他指数，差额可进入同币种或基准币种现金。

## 4. 初始资金部署

`initial_deployment_ratio` 只控制首期风险资产部署。初始化必须区分：

- **建仓期约束**：现金可暂时超过正常上限；
- **正常期约束**：现金进入稳定范围；
- **过渡路径**：按信号、触发器和新增资金逐步完成部署。

这避免初始现金比例和正常现金上限冲突。

## 5. 持续入金

所有外部资金先进入现金资产，再由触发器决定是否部署。新增资金优先用于修复正向仓位缺口，减少主动卖出。

建议执行规则：

```text
new_cash
  → currency cash bucket
  → calculate target gap
  → allocate to underweight assets
  → only sell overweights if cash is insufficient and drift is material
```

入金不改变单位净值，只增加份额。

## 6. Core 配置流程

```text
Strategic base weights
  × Value multiplier
  × Trend multiplier
  × Risk scaling
  → Asset bounds
  → Sleeve/currency bounds
  → Portfolio volatility scaling
  → Turnover limit
  → Cash residual as explicit target
```

优先级：

```text
Hard constraints > Global risk > Asset risk > Trend > Value > Base weights
```

## 7. Satellite 配置流程

Satellite 不等于高风险 Core。它必须产生相对对应基准的净 Alpha：

```text
Alpha scores
  → exposure neutralization
  → liquidity/capacity filters
  → position sizing
  → satellite risk budget
  → overlap check with Core
  → target weights
```

单一策略资金应经过研究、模拟、小资金和正式资金的晋级流程。

## 8. Core 与 Satellite 互调

资金互调分两类：

### 市场风险调整

当系统性风险上升时，Core 和 Satellite 都可以流向现金，Satellite 通常降得更快。

### 策略资本调整

基于较长周期的样本外 Alpha、回撤、相关性和容量评估，对 Satellite 预算进行慢速调整。不得以最近一两个月收益为依据。

建议：

- 评估频率：季度或半年；
- 单次资金预算变化：2–5 个百分点；
- 设定风险贡献上限；
- 所有调整记录决策原因。

## 9. 组合优化器

按复杂度渐进实现：

1. 规则型 VTR + 逆波动；
2. 风险平价或 HRP；
3. 带收缩协方差的约束优化；
4. CVaR / CDaR；
5. Black–Litterman 或稳健优化；
6. 机器学习预期收益，仅作为输入。

优化目标必须包含换手成本和约束，不允许把不稳定预期收益直接放大。

## 10. 目标权重与可执行权重

区分：

- 理论目标权重；
- 风险覆盖后权重；
- 账户与市场限制后的可执行权重；
- 实际成交后权重。

UI 与归因不能混用这些层次。

## 11. 不变量

- 权重和为 1；
- 现金为显式资产；
- 非杠杆模式不允许负权重；
- 单资产、Sleeve、币种和风险贡献不超过上限；
- 交易后现金不能为负；
- 初始部署与正常期约束有独立状态；
- 目标权重变化必须可解释。

## 12. 首版验收

- 支持 CNY/USD 现金；
- 支持持续入金与缺口补仓；
- Core/Satellite 可互调但受治理；
- 所有权重约束有属性测试；
- 输出理论、风险覆盖和可执行三层权重；
- 现金与币种收益可单独归因。

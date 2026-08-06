# 08. 回测与执行系统

## 1. 目标

回测系统要模拟真实决策和执行语义，而不是只把收益矩阵相乘。它必须支持跨市场、现金、多币种、持续入金、事件触发、交易成本和不可交易状态。

## 2. 双引擎架构

### Native Reference Engine

职责：

- 语义简单、确定性强；
- 用于手工验证和 golden test；
- 不追求极致性能；
- 作为 VectorBT/Qlib/实盘结果的对账基准。

### VectorBT Adapter

职责：

- 参数扫描和多资产快速回测；
- 消费统一订单或目标权重；
- 不承载领域逻辑。

未来 Qlib 或 LEAN 也应通过同一 `BacktestEngine` 接口接入。

## 3. 事件顺序

必须明确单日顺序，例如：

1. 读取当时可见的数据；
2. 按统一估值时点更新资产价值；
3. 处理外部现金流并发行/赎回份额；
4. 计算信号和目标权重；
5. 触发器判断是否调仓；
6. 生成卖单和买单；
7. 应用市场可交易性和账户约束；
8. 使用下一可执行价格成交；
9. 扣除成本、税费和汇兑；
10. 计算收盘 NAV、单位净值和诊断。

信号若在收盘后生成，不能按同一收盘价成交。

## 4. 跨市场与时区

- 所有时间内部使用 UTC；
- 每个 Instrument 有交易日历；
- A 股、港股、美股和 BTC 的订单按各自下一可交易时段执行；
- 组合估值和可交易价格分开；
- BTC 周末变动不能触发股票周末成交；
- 汇率使用明确 cut-off。

## 5. 交易成本

统一成本模型：

```text
commission + tax + half spread + slippage + market impact + FX cost
```

成本参数按市场、产品、账户和方向配置。ETF 管理费与跟踪误差可以反映在净值数据中，避免重复扣除。

## 6. 订单模型

至少支持：

- Target weight rebalance；
- Cash amount order；
- Quantity order；
- Market order 模拟；
- Future limit order，后续。

订单必须记录：

- decision_time；
- submitted_time；
- executable_time；
- fill_time；
- requested/filled quantity；
- price、cost、currency；
- rejection reason；
- strategy and decision id。

## 7. 现金与份额会计

外部入金增加份额，不改变单位净值。回测必须满足：

```text
NAV = cash + Σ position_market_value
unit_nav = NAV / units
```

并区分：

- TWR：策略表现；
- XIRR：投资者资金加权收益；
- 期末财富和投资净收益。

## 8. 调仓触发

不是固定月调，而是每日或按数据到达计算，满足以下事件时交易：

- 权重偏离；
- 信号跨档；
- 风险状态变化；
- 新增现金足以形成有效订单；
- 策略预算调整；
- 人工批准的特殊事件。

同时设置冷却期、最小交易金额和最大单次换手。

## 9. 回测结果模型

除 NAV 外至少保存：

- unit NAV、units、cash；
- positions、actual/target/executable weights；
- orders and fills；
- external cash flows；
- transaction costs and turnover；
- FX contribution；
- trigger reasons；
- data/config/code versions；
- validation report。

## 10. 双引擎校验

相同数据、目标权重、订单和成本配置下，对比：

- 每日 NAV；
- 现金和仓位；
- 每笔订单；
- 成交与成本；
- TWR、回撤和换手。

允许的差异必须有显式容差和原因分类，不允许只比较最终收益。

## 11. 实盘迁移

实盘执行采用同一 OrderPlan，区别只在 ExecutionBroker：

```text
Strategy → TargetPortfolio → OrderPlanner
  → PaperBroker / BacktestEngine / LiveBroker
```

上线顺序：影子组合 → 模拟盘 → 只读账户对账 → 小资金人工确认 → 半自动执行。

## 12. 首版验收

- 单日事件顺序有文档和测试；
- 真实数据回测无未来信息；
- 支持持续入金和两种现金币种；
- Native 与 VectorBT 逐日对账；
- 成本和成交时点可配置；
- 输出完整审计链。

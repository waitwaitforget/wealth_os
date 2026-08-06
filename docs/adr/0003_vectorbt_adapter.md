# ADR-0003：VectorBT 仅作为回测适配器

- 状态：Accepted
- 日期：2026-08-05

## 背景

首版选择 VectorBT，但未来 Satellite 可能引入 Qlib，实盘还需要 Broker Adapter。

## 决策

Value、Trend、Risk、Capital Allocation、Accounting 和 Validation 不依赖 VectorBT。VectorBT 只实现统一 BacktestEngine 接口。

## 结果

- 可保留 VectorBT 的研究效率；
- 未来 Qlib 不需要替换全系统；
- 可以用 Native Engine 做交叉校验；
- 需要额外维护适配和统一交易语义。

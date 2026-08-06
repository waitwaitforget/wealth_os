# Architecture Decision Records

ADR 用于记录长期影响较大、难以逆转或存在明确权衡的架构决策。

## 状态

- Proposed；
- Accepted；
- Deprecated；
- Superseded；
- Rejected。

## 规则

1. 一个 ADR 只讨论一个核心决策；
2. 记录背景、备选方案、结果和负面影响；
3. 已接受 ADR 不直接改写历史，变化通过新 ADR 取代；
4. PR 中引用相关 ADR；
5. 金融语义、数据时间和实盘安全决策必须有 ADR。

## 当前 ADR

- [0001 模块化单体与端口适配器](0001_modular_monolith.md)
- [0002 现金作为一级资产](0002_cash_first_class_asset.md)
- [0003 VectorBT 仅作为适配器](0003_vectorbt_adapter.md)
- [0004 Canonical Data Model](0004_canonical_data_model.md)
- [0005 事件触发调仓](0005_event_driven_rebalancing.md)
- [0006 TWR 与 XIRR 双口径](0006_dual_return_accounting.md)

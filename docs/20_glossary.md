# 20. 术语表

## 投资与账户

- **Core**：以长期风险溢价和稳定复利为目标的核心组合。
- **Satellite**：以相对基准 Alpha 为目标的行业、个股或模型策略。
- **Alternative**：BTC 等非传统资产。
- **Cash Asset**：具有币种、收益率和目标权重的现金或现金等价物。
- **External Cash Flow**：投资者对账户的入金或提现，不属于策略收益。
- **Unit NAV**：单位净值，外部现金流只改变份额，不改变该净值。
- **TWR**：时间加权收益，用于衡量策略。
- **XIRR/MWR**：资金加权年化收益，用于衡量投资者实际体验。

## 策略

- **Strategic Weight**：长期战略基准权重。
- **Target Weight**：策略计算的目标权重。
- **Executable Weight**：考虑账户和市场限制后的可执行权重。
- **VTR**：Value–Trend–Risk 组合框架。
- **Risk Overlay**：在原始策略权重之上施加的组合风险调整。
- **Rebalance Trigger**：导致交易的事件条件。
- **Drift**：实际权重与目标权重的偏离。

## 风险

- **Volatility Targeting**：按预测波动率缩放风险仓位。
- **Risk Contribution**：资产对组合总风险的边际贡献。
- **Maximum Drawdown**：从历史高点到后续低点的最大跌幅。
- **CDaR**：最差一部分回撤的平均风险度量。
- **Expected Shortfall**：超过 VaR 阈值后的平均尾部损失。
- **Risk Budget**：某资产、策略或风险因子允许贡献的风险上限。

## 数据与研究

- **Point-in-Time**：只使用历史时点当时已知的数据。
- **Canonical Data**：跨供应商统一后的标准数据模型。
- **Feature**：直接计算的观测量。
- **Factor**：有经济含义并经过处理的信号。
- **Walk-forward**：按时间滚动训练/设定并在未来区间验证。
- **Ablation**：关闭某模块以测量其独立贡献。
- **Look-ahead Bias**：使用未来信息导致的回测偏差。
- **Survivorship Bias**：只保留当前存续标的导致的偏差。

## 工程与治理

- **ADR**：Architecture Decision Record，架构决策记录。
- **Adapter**：把外部框架转换为内部稳定接口的实现。
- **Golden Test**：固定输入和人工可审查输出的回归测试。
- **Shadow Portfolio**：完全按模型运行但不真实成交的影子组合。
- **Kill Switch**：阻止或停止实盘执行的紧急控制。
- **Data Version**：可唯一定位输入数据快照的版本。
- **Strategy Version**：可唯一定位规则、模型和参数的版本。

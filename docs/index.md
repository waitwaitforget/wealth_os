# Wealth OS 文档中心

> **Wealth OS 的目标不是预测市场，而是在不确定性中持续做出更优、可解释、可验证的资本配置决策。**

Wealth OS 是面向个人长期投资者的多资产财富管理系统。系统以宽基资产配置为 Core，以行业和个股 Alpha 为 Satellite，将现金、债券、黄金和数字资产视为正式资产，并将数据治理、策略验证、风险控制、持续入金和投资决策解释纳入同一套架构。

## 文档地图

| 领域 | 文档 | 主要回答的问题 |
|---|---|---|
| 愿景 | [00 Vision](00_vision.md) | 为什么做、做成什么、不做什么 |
| 架构 | [01 Architecture](01_architecture.md) | 系统怎样分层，模块如何协作 |
| 工程 | [02 Engineering System](02_engineering_system.md) | 如何保证项目长期可维护 |
| 目录 | [03 Project Structure](03_project_structure.md) | 代码、配置、数据和文档放在哪里 |
| 数据 | [04 Data OS](04_data_os.md) | 多市场数据如何获取、清洗、版本化 |
| 研究 | [05 Research & Factor OS](05_research_factor_os.md) | 因子如何定义、生产、验证和组合 |
| 组合 | [06 Portfolio & Capital OS](06_portfolio_capital_os.md) | Core、Satellite、现金和入金怎样分配 |
| 风险 | [07 Risk Management](07_risk_management.md) | 风险预算、回撤、汇率和集中度怎样控制 |
| 回测 | [08 Backtest & Execution](08_backtest_execution.md) | 回测、成本、订单和实盘语义如何统一 |
| 校验 | [09 Validation & Governance](09_validation_governance.md) | 如何证明数据、策略和实现没有明显错误 |
| 决策 | [10 Decision Engine](10_decision_engine.md) | 如何把模型结果转化为可解释动作 |
| 模拟 | [11 Simulation & Forecasting](11_simulation_forecasting.md) | 如何做压力测试、可信区间和财富路径预测 |
| API | [12 API Contracts](12_api_contracts.md) | 后端模块和前端如何稳定集成 |
| UI | [13 UI/UX](13_ui_ux.md) | 移动端如何展示收益、风险与建议 |
| 安全 | [14 Security & Privacy](14_security_privacy.md) | 密钥、账户与个人数据如何保护 |
| 运维 | [15 Observability & Operations](15_observability_operations.md) | 系统怎样持续运行、报警和恢复 |
| 部署 | [16 Deployment](16_deployment.md) | 本地、服务端和未来实盘如何部署 |
| 路线图 | [17 Roadmap](17_roadmap.md) | 短期和长期 Milestone 是什么 |
| 测试 | [18 Testing Strategy](18_testing_strategy.md) | 每层应该怎样测试和验收 |
| Git | [19 Git Governance](19_git_governance.md) | 分支、提交、PR 和发布怎样管理 |
| 术语 | [20 Glossary](20_glossary.md) | 系统术语、金融口径和缩写定义 |
| 交接 | [21 Codex Handoff](21_codex_handoff.md) | 今晚切换 Codex 后从哪里开始 |

## 架构决策记录

所有不可轻易逆转或会影响多个模块的决策，都应记录为 ADR。见 [ADR 索引](adr/README.md)。

## 当前实现状态

仓库当前已有一个可运行的 V1 原型，包括：

- 现金作为一级可投资资产；
- Core、Satellite、Alternative 和 Cash 的领域模型；
- 价值、趋势、波动率因子原型；
- 事件触发调仓；
- 持续入金、单位净值、TWR 与 XIRR；
- 原生确定性回测器和 VectorBT 适配边界；
- 会计、权重和无未来信息校验。

当前实现仍属于**研究骨架**，不应直接用于真实资金决策。真实市场数据、跨市场日历、双币种账本、完整交易成本、样本外验证、影子组合和实盘对账必须完成后，才能进入小资金验证阶段。

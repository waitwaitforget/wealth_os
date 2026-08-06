# Wealth OS Development Plan

> **Project goal**
>
> Wealth OS 的目标不是预测市场，而是在不确定性下，持续做出更优、可解释、可验证的长期资本配置决策。

---

## 1. 当前状态

当前项目已完成：

- V1 领域模型与基础模块骨架
- 现金作为正式资产
- Core / Satellite / Alternative / Cash 基础账本
- 初始资金部署比例
- 持续入金与单位净值
- TWR / XIRR
- 价值、趋势、风险因子基础实现
- 事件触发式调仓骨架
- 交易成本模型
- 自研参考回测器
- VectorBT 适配器接口
- 基础 Validation
- 完整 `docs/` 设计文档体系
- P0 工程化规划

下一阶段不应继续堆叠策略，而应优先完成真实数据体系。

---

# 2. 总体 Roadmap

```text
P0 Engineering Foundation
        ↓
P1 Data OS
        ↓
P2 Research / Factor OS
        ↓
P3 Portfolio OS
        ↓
P4 Validation OS
        ↓
P5 Backtest & Benchmark
        ↓
P6 Decision Engine
        ↓
P7 Scenario Simulator
        ↓
P8 Mobile Dashboard
        ↓
P9 Paper Trading / Live Integration
```

---

# 3. P0：工程体系建设

## 3.1 目标

让项目具备长期维护 3–5 万行代码的工程能力。

## 3.2 主要任务

- [ ] 初始化 Git 仓库
- [ ] 建立 `main` / `develop` / `feature/*` 分支策略
- [ ] 使用 `uv` 管理 Python 与依赖
- [ ] 完成 `pyproject.toml`
- [ ] 配置 Ruff
- [ ] 配置 Black
- [ ] 配置 MyPy
- [ ] 配置 Pytest 与 Coverage
- [ ] 配置 pre-commit
- [ ] 配置 GitHub Actions
- [ ] 建立 Docker 开发环境
- [ ] 建立 Pydantic Settings 配置系统
- [ ] 引入 Structlog
- [ ] 建立 MkDocs Material 文档站
- [ ] 建立 Issue / PR 模板
- [ ] 建立 Conventional Commits 规范
- [ ] 建立 ADR 工作流
- [ ] 清理现有 demo、缓存、临时代码和目录结构

## 3.3 验收标准

- `uv sync` 可完成依赖安装
- `pytest` 全部通过
- `ruff check .` 通过
- `mypy src` 通过
- GitHub Actions 自动执行 lint、test、coverage
- 文档站可本地启动
- 新增模块有明确目录和依赖边界
- `domain` 层不依赖 VectorBT、Qlib、FastAPI 等基础设施

---

# 4. P1：Data OS

## 4.1 目标

把系统从 Synthetic Demo 升级为可复现、可追踪、可校验的真实市场数据平台。

## 4.2 首批资产范围

### A 股

- 沪深 300
- 中证 500
- 中证红利

### 港股

- 恒生指数
- 恒生国企指数
- 恒生科技指数

### 美股

- 标普 500
- 纳斯达克 100

### 防御资产

- 人民币现金或短债代理
- 美元现金或短债代理
- 黄金

### 另类资产

- BTC

### 汇率

- USD/CNY
- HKD/CNY

## 4.3 首批数据源

建议初期保持少而稳定：

- AKShare / Tushare：A 股、港股
- Yahoo Finance 或等价数据源：美股、ETF、BTC
- FRED：美元利率、宏观和现金收益率
- 后续增加商业数据源作为主数据或校验数据

## 4.4 统一数据模型

至少包含：

```text
instrument_id
symbol
market
asset_class
currency
timestamp
open
high
low
close
adjusted_close
volume
dividend
split_factor
source
effective_time
ingestion_time
revision_version
```

## 4.5 主要任务

### Domain Models

- [ ] 定义 `Instrument`
- [ ] 定义 `BarData`
- [ ] 定义 `CorporateAction`
- [ ] 定义 `FXRate`
- [ ] 定义 `InterestRate`
- [ ] 定义 `TradingCalendar`
- [ ] 定义 `DataVersion`
- [ ] 定义 `DataQualityReport`

### Storage

- [ ] 设计 `raw/processed/features/snapshots` 分层
- [ ] 使用 Parquet 存储
- [ ] 使用 DuckDB 查询
- [ ] 支持按数据源和版本读取
- [ ] 支持增量更新
- [ ] 支持历史快照
- [ ] 禁止静默覆盖历史数据

### Providers

- [ ] 定义统一 `MarketDataProvider` 协议
- [ ] 实现一个 A 股 Provider
- [ ] 实现一个美股 Provider
- [ ] 实现 BTC Provider
- [ ] 实现 FX Provider
- [ ] 实现利率 Provider
- [ ] 增加 Provider 重试、限流和缓存

### Data Processing

- [ ] 复权处理
- [ ] 分红处理
- [ ] 拆股处理
- [ ] 多市场时区归一
- [ ] 交易日历对齐
- [ ] 休市与缺失值处理
- [ ] BTC 24×7 与股票日历映射
- [ ] 人民币统一计价
- [ ] 本币收益和汇率收益拆分

### Data Validation

- [ ] Schema 校验
- [ ] 唯一性校验
- [ ] 缺失数据校验
- [ ] 重复数据校验
- [ ] OHLC 合法性校验
- [ ] 极端价格跳变校验
- [ ] 复权连续性校验
- [ ] 多数据源抽样对账
- [ ] Point-in-Time 校验
- [ ] 数据版本可复现性测试

## 4.6 验收标准

- 任意回测可以固定数据版本复现
- 数据更新可增量执行
- 同一日期同一标的不存在重复主记录
- OHLC 和复权关系符合规则
- 价格异常和缺失可自动报告
- 收盘后生成的信号不会按同一收盘价成交
- A 股、港股、美股、BTC 与汇率拥有明确统一时间语义
- 可以输出一份真实数据健康报告
- 可以使用真实价格重跑当前 demo

## 4.7 P1 第一批 Codex 任务

1. 实现标准领域模型
2. 实现 Parquet + DuckDB Repository
3. 定义 Provider Protocol
4. 接入一个 A 股资产
5. 接入一个美股资产
6. 接入 BTC
7. 接入 USD/CNY
8. 实现数据质量 CLI
9. 生成首份数据健康报告
10. 使用真实价格运行现有基础回测

> P1 阶段不以策略收益为目标。首要目标是证明输入数据可靠。

---

# 5. P2：Research / Factor OS

## 5.1 目标

建立可解释、可复用、无未来信息泄漏的因子生产体系。

## 5.2 Value Factors

- [ ] PE Earnings Yield
- [ ] PB Inverse
- [ ] Dividend Yield
- [ ] Equity Risk Premium
- [ ] CAPE 或近似长期估值
- [ ] 历史估值分位
- [ ] 横截面估值分位
- [ ] 多指标综合 Value Score

## 5.3 Trend Factors

- [ ] 3M Momentum
- [ ] 6M Momentum
- [ ] 12M Momentum
- [ ] 12M-1M Momentum
- [ ] 200 日均线状态
- [ ] 均线斜率
- [ ] 多周期趋势共识
- [ ] 距离历史高点
- [ ] 下行趋势强度

## 5.4 Risk Factors

- [ ] 20 日波动率
- [ ] 60 日波动率
- [ ] 252 日波动率
- [ ] 下行波动率
- [ ] 最大回撤
- [ ] Ulcer Index
- [ ] Rolling Correlation
- [ ] VaR
- [ ] Expected Shortfall
- [ ] Marginal Risk Contribution

## 5.5 Factor Infrastructure

- [ ] 统一 Factor Protocol
- [ ] Factor Registry
- [ ] 参数版本管理
- [ ] 因子缓存
- [ ] 因子快照
- [ ] 因子血缘
- [ ] 因子可解释元数据
- [ ] 因子分层和标准化
- [ ] 不同市场独立历史分位

## 5.6 验收标准

每个因子必须具备：

- 单元测试
- 手算样例
- 单调性测试
- 边界测试
- 缺失值策略
- 延迟输入测试
- Point-in-Time 测试
- 参数邻域稳定性测试
- 因子解释文档

---

# 6. P3：Portfolio OS

## 6.1 目标

把因子转化为稳定、可解释、受风险约束的目标仓位。

## 6.2 第一版组合逻辑

```text
战略基准权重
× 价值调整
× 趋势调整
× 风险缩放
→ 原始目标权重
→ 组合约束
→ 现金权重
→ 可执行目标权重
```

## 6.3 主要任务

### Capital Manager

- [ ] 初始资金部署比例
- [ ] 持续入金
- [ ] 入金先进入对应币种现金池
- [ ] 新资金优先修复低配资产
- [ ] 资金部署与资产配置分离
- [ ] 人民币与美元双现金池
- [ ] 现金收益率

### Core / Satellite / Alternative

- [ ] Core / Satellite 可互调
- [ ] 战略中枢与允许区间
- [ ] BTC 独立风险预算
- [ ] Core / Satellite 风险贡献
- [ ] 全局穿透暴露

### Constraints

- [ ] 单资产上限
- [ ] 单市场上限
- [ ] 单币种上限
- [ ] 单行业上限
- [ ] BTC 上限
- [ ] 现金上下限
- [ ] 总权益上下限
- [ ] 禁止负现金和非法杠杆

### Risk Overlay

- [ ] 目标波动率
- [ ] 回撤状态机
- [ ] 相关性冲击
- [ ] 风险贡献上限
- [ ] 快速降风险
- [ ] 缓慢恢复风险

### Optimizers

第一阶段：

- [ ] 规则型 VTR
- [ ] 逆波动率
- [ ] 风险平价

后续：

- [ ] HRP
- [ ] Minimum Variance
- [ ] CVaR
- [ ] Black-Litterman
- [ ] Robust Optimization

## 6.4 验收标准

- 权重和恒等于 1
- 现金为显式持仓
- Core 降仓不必自动流向其他指数
- 新资金不会污染策略收益
- 所有权重约束始终成立
- 资产评分与组合评分可分别解释
- 同一输入可稳定复现同一目标仓位

---

# 7. P4：Validation OS

## 7.1 目标

证明系统实现与设计一致，数据和会计口径正确，策略结果具备统计稳健性。

## 7.2 校验层级

### Data Validation

- [ ] Schema
- [ ] 多源对账
- [ ] 时间语义
- [ ] 复权
- [ ] 数据版本
- [ ] Point-in-Time

### Factor Validation

- [ ] 单元测试
- [ ] 单调性
- [ ] 边界行为
- [ ] 无未来信息
- [ ] 参数邻域

### Portfolio Validation

- [ ] 权重约束
- [ ] 资金守恒
- [ ] 交易守恒
- [ ] 风险预算
- [ ] 现金非负

### Accounting Validation

- [ ] NAV 恒等式
- [ ] 份额净值
- [ ] TWR
- [ ] XIRR
- [ ] 入金和投资损益分离
- [ ] 交易成本归因

### Backtest Validation

- [ ] 自研引擎与 VectorBT 双引擎对账
- [ ] 日级 NAV 对账
- [ ] 持仓对账
- [ ] 订单对账
- [ ] 成本对账
- [ ] 未来接入 Qlib / LEAN 对账

### Statistical Validation

- [ ] Walk-forward
- [ ] 多起点测试
- [ ] 参数敏感性
- [ ] 模块消融
- [ ] 成本压力
- [ ] 数据扰动
- [ ] 延迟成交
- [ ] Bootstrap
- [ ] Backtest Overfitting 记录

### Live Governance

- [ ] Shadow Portfolio
- [ ] Paper Trading
- [ ] 策略晋级
- [ ] 策略降级
- [ ] 策略暂停
- [ ] 策略恢复
- [ ] 策略版本审计

## 7.3 验收标准

- 会计恒等式每日成立
- 双引擎误差在明确容差内
- 参数附近表现稳定
- 收益不是单个时期或单个参数造成
- 交易成本翻倍后策略仍具基本有效性
- Shadow Portfolio 可以区分模型问题和执行问题

---

# 8. P5：Backtest & Benchmark

## 8.1 目标

建立正式的真实市场回测、基准比较和归因体系。

## 8.2 基准

### Core

- 固定战略配置
- 三地宽基固定配置
- 现金或短债基准

### Satellite

- 对应市场基准
- 对应行业基准
- 风格中性基准

### 总组合

- 相同风险水平固定配置
- 80/20 静态 Core-Satellite

## 8.3 指标

- TWR
- XIRR
- CAGR
- Annualized Return
- Volatility
- Downside Volatility
- Maximum Drawdown
- CDaR
- Sharpe
- Sortino
- Calmar
- Expected Shortfall
- Recovery Time
- Turnover
- Trading Cost
- Currency Contribution
- Cash Contribution
- Signal Attribution

## 8.4 验收标准

- 明确显示回测起止日期
- 明确标注真实数据或合成数据
- 输出累计收益和年化收益
- 输出交易成本前后收益
- 输出与固定基准差异
- 输出每个模块贡献

---

# 9. P6：Decision Engine

## 9.1 目标

把目标权重转化为人可以理解和执行的决策。

## 9.2 输出结构

```text
资产
当前仓位
目标仓位
建议变化
触发原因
价值贡献
趋势贡献
风险贡献
组合约束贡献
置信等级
预计成本
执行优先级
```

## 9.3 主要任务

- [ ] Decision DTO
- [ ] 决策解释
- [ ] 决策置信度
- [ ] 不操作解释
- [ ] 决策日志
- [ ] 历史决策复盘
- [ ] 建议与实际执行偏差

---

# 10. P7：Scenario Simulator

## 10.1 目标

展示策略在极端和常见场景下的组合行为，而不是只展示历史结果。

## 10.2 场景

- 美股下跌 20%
- 港股下跌 25%
- A 股下跌 20%
- BTC 下跌 50%
- 人民币升值或贬值 10%
- 股票债券同时下跌
- 全球相关性升至 0.8
- 持续入金中断
- 突发大额入金
- 高波动率持续

## 10.3 输出

- 组合预计损失区间
- 风险贡献变化
- 现金变化
- 触发器变化
- 预计调仓动作
- 恢复路径
- 可信区间

---

# 11. P8：Mobile Dashboard

## 11.1 目标

提供移动端友好、可解释、可执行的资产管理界面。

## 11.2 页面

- 总资产
- Core / Satellite / BTC / Cash
- 市场温度
- 风险中心
- 组合仓位
- 调仓建议
- 收益与本金拆分
- TWR / XIRR
- 汇率贡献
- 策略健康度
- 决策日志
- 情景模拟
- 数据健康报告

## 11.3 技术栈

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- ECharts / Plotly
- PWA
- FastAPI

---

# 12. P9：Paper Trading / 实盘接入

## 12.1 目标

建立从模型目标权重到真实成交结果的完整闭环。

## 12.2 主要任务

- [ ] Paper Broker
- [ ] Order Planner
- [ ] 可执行目标权重
- [ ] 订单生成
- [ ] 人工审批
- [ ] 成交回写
- [ ] 实际与模型仓位对账
- [ ] 实际滑点分析
- [ ] 实际费用归因
- [ ] 实盘异常报警
- [ ] 券商适配器

## 12.3 上线顺序

```text
历史回测
→ Walk-forward
→ Shadow Portfolio
→ Paper Trading
→ 1% 资金
→ 3% 资金
→ 正式风险预算
```

---

# 13. 近期执行计划

工程体系完成后，严格按以下顺序推进：

## Sprint 1：Data Domain

- [ ] Instrument
- [ ] BarData
- [ ] FXRate
- [ ] TradingCalendar
- [ ] DataVersion
- [ ] DataQualityReport

## Sprint 2：Storage

- [ ] Parquet Repository
- [ ] DuckDB Query Layer
- [ ] Data Versioning
- [ ] Incremental Update

## Sprint 3：Providers

- [ ] A 股
- [ ] 美股
- [ ] BTC
- [ ] USD/CNY
- [ ] 利率

## Sprint 4：Validation

- [ ] Schema Check
- [ ] Duplicate Check
- [ ] Missing Check
- [ ] Price Integrity
- [ ] Cross-source Check
- [ ] Point-in-Time Check

## Sprint 5：Real-data Demo

- [ ] 使用真实价格运行
- [ ] 显示数据区间
- [ ] 显示累计收益
- [ ] 显示年化收益
- [ ] 明确标注数据源
- [ ] 输出 Data Health Report

---

# 14. 开发边界

## 必须遵守

- `domain` 不依赖基础设施
- Notebook 不承载生产逻辑
- 数据不静默覆盖
- 所有策略结果可复现
- 所有输入有版本
- 所有决策可解释
- 所有回测显示时间区间
- 真实数据和 demo 数据明确区分
- 现金是正式资产
- 入金不能污染策略收益
- 先校验正确，再讨论优化收益

## 暂不实现

- 高频交易
- 杠杆
- 期权
- 做空
- 复杂 RL
- 自动实盘
- 黑盒深度学习择时
- 高频汇率择时

---

# 15. Definition of Done

一个模块只有满足以下要求才算完成：

- 有清晰职责和接口
- 有类型注解
- 有单元测试
- 有边界测试
- 有文档
- 有日志
- 有配置
- 有失败处理
- 有可复现实例
- 通过 CI
- 不破坏现有领域边界
- 能在未来替换实现而不影响上层调用

---

# 16. 最终原则

> Wealth OS 的短期目标不是立即找到最高收益策略。

> 短期目标是建立一套数据可信、逻辑正确、收益可解释、风险可控制、结果可复现的长期投资基础设施。

只有在此基础上，策略收益、Alpha、机器学习和自动化投资才有意义。

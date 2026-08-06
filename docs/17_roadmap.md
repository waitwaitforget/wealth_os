# 17. 产品与技术路线图

## 1. 路线原则

每个 Milestone 都必须形成可运行、可验证的增量，不以代码量作为完成标准。业务功能进入下一阶段前，前一阶段的质量门禁必须稳定。

## P0：工程体系与仓库治理

### 目标

让项目具备长期维护能力。

### 范围

- uv + pyproject；
- DDD/模块化目录；
- Ruff、mypy、pytest、Hypothesis、coverage；
- pre-commit；
- GitHub Actions；
- MkDocs；
- structlog；
- Pydantic 配置；
- Docker Compose；
- Issue/PR 模板、CODEOWNERS、ADR；
- 清理缓存和生成文件。

### 完成标准

新开发者能按 README 在 15 分钟内运行测试、demo 和文档；所有 PR 通过自动门禁。

## P1：Data OS

### 目标

用真实、可版本化的多市场数据替代合成数据。

### 范围

- Instrument Master；
- A/H/US 宽基、债券、黄金、BTC、现金收益和 FX；
- Raw/Canonical/PIT；
- 交易日历和时区；
- 双源检查；
- 数据健康报告。

### 完成标准

真实数据可重复下载和处理，回测绑定数据版本，无明显前视和复权错误。

## P2：Core Research OS

### 目标

形成研究级 Value/Trend/Risk 因子。

### 范围

- 因子规范、元数据和版本；
- Value、Trend、Risk 多指标；
- 因子健康和无未来信息测试；
- 消融、参数邻域和 Walk-forward 基础。

### 完成标准

每个因子可解释、可复现，并有独立贡献分析。

## P3：Portfolio & Capital OS

### 目标

完成现金感知、持续入金、多币种和风险预算配置。

### 范围

- CNY/USD 现金池；
- Core/Satellite/Alternative 动态预算；
- 初始部署状态机；
- 缺口补仓；
- 风险平价/HRP 基线；
- 理论、风险覆盖和可执行权重。

### 完成标准

随机状态下所有约束始终成立，资金和风险归因完整。

## P4：Backtest & Validation OS

### 目标

建立可信回测和自动质量门禁。

### 范围

- 跨市场事件顺序；
- 完整成本；
- Native/VectorBT 双引擎；
- 会计和订单对账；
- Walk-forward、Bootstrap、压力和消融；
- Health Report。

### 完成标准

双引擎逐日结果在容差内；关键策略通过样本外与成本压力测试。

## P5：Decision OS 与移动端 MVP

### 目标

将研究结果变成可理解、可审核的行动建议。

### 范围

- Decision Schema；
- 贡献解释；
- No Action；
- FastAPI；
- Next.js PWA；
- Overview、Portfolio、Risk、Decision、Validation 页面。

### 完成标准

用户能在移动端理解资产、收益口径、风险和建议原因。

## P6：Shadow Portfolio 与真实账户对账

### 目标

在不自动交易的情况下验证系统与真实市场。

### 范围

- 每日影子组合；
- 实际账户导入；
- 模型/实际/基准归因；
- 数据和执行偏差监控；
- 策略审查状态机。

### 完成标准

连续运行至少 3–6 个月，账户对账稳定，无关键校验错误。

## P7：Satellite 行业与个股 Alpha

### 目标

扩展 20% Satellite。

### 范围

- 行业 ETF 轮动；
- 个股 Point-in-Time 基本面；
- Qlib 数据和实验适配；
- LightGBM 基线；
- 风格中性化、容量和成本；
- 策略晋级机制。

### 完成标准

净 Alpha 在样本外和影子组合中可验证，风险与 Core 重叠受控。

## P8：半自动执行

### 目标

从建议到人工批准订单。

### 范围

- Broker read-only；
- OrderPlan；
- 人工审批；
- 小资金执行；
- 实盘回写、幂等和 Kill switch。

### 完成标准

在严格限额下完成小资金闭环，实际成交与预估偏差可解释。

## P9：高级模拟与智能研究

- Regime simulation；
- 可信区间改进；
- Agent 辅助研究和报告；
- 模型漂移诊断；
- 不自动放宽风险或审批边界。

## 长期不承诺时间的方向

- 生成式研究助手；
- 多策略资本分配；
- 税务优化；
- 更多账户与家庭资产负债表；
- 受控的自动执行。

## 优先级准则

遇到冲突时：

```text
Correctness > Risk control > Reproducibility > Explainability > Performance > Feature breadth
```

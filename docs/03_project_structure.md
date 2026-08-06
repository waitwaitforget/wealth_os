# 03. 项目目录与模块边界

## 1. 目标目录

```text
wealth-os/
├── src/wealth_os/
│   ├── domain/
│   ├── application/
│   ├── research/
│   ├── portfolio/
│   ├── risk/
│   ├── accounting/
│   ├── validation/
│   ├── infrastructure/
│   │   ├── data/
│   │   ├── persistence/
│   │   ├── backtest/
│   │   ├── execution/
│   │   └── notifications/
│   └── presentation/
│       ├── api/
│       └── cli/
├── apps/web/
├── configs/
├── data/
│   ├── raw/
│   ├── canonical/
│   ├── features/
│   └── artifacts/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── property/
│   └── fixtures/
├── docs/
├── notebooks/
├── examples/
├── scripts/
├── docker/
└── .github/
```

## 2. 模块职责

### `domain/`

稳定的领域模型与协议。不得包含数据库、HTTP、DataFrame 读写或外部 SDK 细节。

### `application/`

用例编排，例如 `RunBacktestService`、`GenerateDecisionService` 和 `UpdateMarketDataService`。

### `research/`

特征、因子、标签、数据集和实验逻辑。可以依赖数值库，但不直接访问远端数据源。

### `portfolio/`

资本分配、资产配置、约束优化、调仓和仓位管理。

### `risk/`

组合风险、风险预算、压力状态、回撤与汇率覆盖。

### `accounting/`

现金流、份额、NAV、订单、成交、成本和收益核算。

### `validation/`

所有质量规则、验证报告和发布门禁。

### `infrastructure/`

外部系统实现。适配器可以依赖第三方库，但必须实现 Domain 或 Application 定义的接口。

### `presentation/`

API、CLI 和未来通知入口。不得直接实现策略计算。

## 3. Import 规则

允许方向：

```text
presentation → application → domain
infrastructure → application/domain
research/portfolio/risk/accounting → domain
application → research/portfolio/risk/accounting interfaces
```

禁止方向：

- `domain → infrastructure`；
- `domain → vectorbt/qlib/fastapi`；
- `research → presentation`；
- `portfolio → broker SDK`；
- `UI → database`。

建议通过 `import-linter` 自动检查。

## 4. Notebook 规则

Notebook 仅用于探索、可视化和一次性诊断：

- 所有可复用逻辑必须迁移到 `src/`；
- Notebook 必须声明数据版本和配置；
- 输出不作为正式研究结论的唯一来源；
- 不提交大体积输出和敏感信息；
- 稳定实验转为脚本或测试。

## 5. 数据目录规则

- `raw/` 不可变，只追加；
- `canonical/` 由确定性转换生成；
- `features/` 与因子代码版本绑定；
- `artifacts/` 保存回测、模型和报告；
- 大数据不直接进入 Git；
- 小型固定测试数据可存放在 `tests/fixtures/`。

## 6. 命名约定

- 模块和函数使用 `snake_case`；
- 领域类使用 `PascalCase`；
- 币种使用 ISO 4217；
- 标的使用内部稳定 `instrument_id`，不直接用供应商代码作为主键；
- 时间字段明确后缀：`event_time`、`effective_time`、`ingested_at`；
- 收益率用小数，不用百分数存储；
- 货币金额明确币种或以 Money 值对象表达。

## 7. 当前仓库迁移建议

当前 `factors/`、`allocation/`、`backtest/` 等目录不需要一次性推倒。采用小步迁移：

1. 先新增 Application 和 Infrastructure 边界；
2. 将外部依赖迁入 Infrastructure；
3. 将收益核算迁入 Accounting；
4. 把原有模块保留兼容导入一个版本；
5. 完成测试后删除旧路径。

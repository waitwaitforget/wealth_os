# 21. Codex 开发交接与 P0 执行清单

## 1. 当前状态

当前仓库是可运行的研究原型，包含合成数据、VTR 配置原型、事件触发调仓、持续入金、单位净值、原生回测器和基础 Validation。文档已经定义目标架构，但代码尚未完全迁移到该架构。

当前结果只能用于工程和金融语义验证，不能视为真实策略收益。

## 2. Codex 开始前必须阅读

按顺序阅读：

1. `docs/00_vision.md`；
2. `docs/01_architecture.md`；
3. `docs/02_engineering_system.md`；
4. `docs/03_project_structure.md`；
5. `docs/09_validation_governance.md`；
6. `docs/17_roadmap.md`；
7. `docs/19_git_governance.md`；
8. `docs/adr/` 下所有 Accepted ADR。

## 3. 不可破坏的边界

- Domain 不得依赖 VectorBT、Qlib、FastAPI 或数据源 SDK；
- 现金必须是显式资产，权重总和必须包含现金；
- 所有外部入金通过份额处理，不污染单位净值；
- TWR、XIRR 和财富增长必须分开；
- 信号生成与成交时点不能形成未来信息；
- 正式结果必须绑定数据、配置和代码版本；
- Validation Error 可以阻断决策和执行；
- 合成 Demo 必须明显标注，不能呈现为真实业绩。

## 4. P0 推荐 Issue 顺序

### P0-01：仓库清理

- 删除 `__pycache__`、`.pytest_cache` 和生成文件；
- 完善 `.gitignore`；
- 添加 `.editorconfig`；
- 保证干净 clone 后可运行。

### P0-02：迁移到 uv

- Python 固定为 3.12；
- 更新 `pyproject.toml`；
- 创建 `uv.lock`；
- 依赖分组：core、dev、docs、research；
- README 更新安装命令。

### P0-03：代码质量工具

- Ruff format/lint；
- mypy；
- pytest-cov；
- Hypothesis；
- pre-commit；
- `make ci` 或 `just ci`。

### P0-04：GitHub Actions

- lint；
- type check；
- unit tests；
- coverage；
- docs build；
- dependency/security scan。

### P0-05：配置与日志

- Pydantic Settings；
- YAML 配置加载；
- 配置 hash；
- structlog 和 run context；
- `.env.example`。

### P0-06：目录迁移

采用小步迁移，不一次重写：

- 建立 `application/`、`infrastructure/`、`accounting/`；
- 定义接口；
- 迁移现有模块；
- 保留兼容导入一个版本；
- 使用 import-linter。

### P0-07：文档站与治理文件

- 安装 MkDocs Material；
- 文档构建进入 CI；
- 添加 `CONTRIBUTING.md`；
- PR/Issue 模板；
- `CODEOWNERS`；
- ADR 流程。

## 5. 每个 Codex 任务的提示模板

```text
Read these files first:
- docs/...
- relevant ADRs
- existing tests

Implement only Issue P0-XX.
Do not change financial semantics outside the issue.
Keep domain independent from external frameworks.
Add tests before or with the implementation.
Run: make ci
Return:
1. summary
2. changed files
3. financial/architecture impact
4. test output
5. remaining risks
```

## 6. PR 大小

- 单个 PR 尽量少于 500 行实质代码；
- 纯机械目录迁移可例外，但不与行为变更混合；
- 金融语义变化单独 PR；
- 每个 PR 只完成一个可验收目标。

## 7. P0 完成定义

P0 完成后应满足：

```bash
uv sync --all-groups
make ci
make docs
make demo
```

全部成功；新环境不需要手工修补路径；`main` 受到保护；文档和测试成为合并门禁；当前 6 个测试保持通过，并新增工程门禁测试。

## 8. 进入 P1 前禁止事项

- 不接入真实券商下单；
- 不增加复杂机器学习模型；
- 不优化 Demo 收益；
- 不进行大规模参数扫描；
- 不建设复杂微服务；
- 不在工程体系未完成时继续扩张业务代码。

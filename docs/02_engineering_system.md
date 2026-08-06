# 02. 工程体系设计

## 1. 目标

工程体系必须支撑未来数万行代码、多个数据源、多个策略版本和长期运行。核心要求是：可复现、可测试、可审查、可升级、可回滚。

## 2. 基础技术选择

| 领域 | 推荐 | 原因 |
|---|---|---|
| Python | 3.12+ | 类型系统、性能和生态成熟 |
| 包管理 | uv | 快速、锁文件清晰、统一虚拟环境 |
| 构建 | hatchling 或 setuptools | 保持标准 Python 包兼容性 |
| 数据框 | Polars 为主，Pandas 兼容 | Polars 适合大数据，Pandas 兼容量化生态 |
| 数值 | NumPy / SciPy | 标准数值计算 |
| 存储 | Parquet + DuckDB | 本地分析、高压缩、可查询 |
| 配置 | Pydantic Settings + YAML | 类型化、可校验、环境覆盖 |
| 日志 | structlog | 结构化、上下文绑定 |
| 测试 | pytest + hypothesis + coverage | 单元、属性和覆盖率 |
| 静态检查 | Ruff + mypy | 快速且严格 |
| 文档 | MkDocs Material | Markdown 原生、导航和搜索 |
| CI | GitHub Actions | 自动质量门禁 |

## 3. 开发环境

### 必须提供

- `uv.lock`；
- `.python-version`；
- `Makefile` 或 `justfile`；
- `.pre-commit-config.yaml`；
- `.editorconfig`；
- `.env.example`；
- Dockerfile 与 compose 开发环境；
- VS Code 推荐配置，可选。

### 标准命令

```bash
make setup       # 安装依赖和 pre-commit
make lint        # ruff + mypy
make test        # pytest
make coverage    # 生成覆盖率
make docs        # 本地文档站
make demo        # 运行可重复 demo
make ci          # 与 CI 完全一致的本地门禁
```

## 4. 依赖治理

- 生产依赖、研究依赖、UI 依赖和开发依赖分组；
- 核心领域依赖必须尽可能少；
- Qlib、VectorBT、数据 SDK 等重依赖全部可选安装；
- 每月运行依赖更新 PR，但不自动合并；
- 重大版本升级必须有回归报告；
- 禁止在 Notebook 中隐式安装包。

建议分组：

```toml
[dependency-groups]
dev = [...]
research = ["vectorbt", "cvxpy", ...]
data-cn = ["akshare", "tushare", ...]
ml = ["pyqlib", "lightgbm", ...]
api = ["fastapi", "uvicorn", ...]
```

## 5. 配置系统

配置必须区分：

- 应用环境配置；
- 数据源配置；
- 资产 Universe；
- 策略参数；
- 风险约束；
- 回测执行语义；
- 用户账户和现金流场景。

每次运行计算配置哈希并写入结果。禁止在代码中散落魔法数字。

```text
configs/
  base.yaml
  environments/local.yaml
  universes/core_global.yaml
  strategies/vtr_v1.yaml
  risk/balanced.yaml
  scenarios/monthly_contribution.yaml
```

## 6. 日志与运行上下文

每条关键日志至少包含：

- `run_id`；
- `strategy_id` 与版本；
- `data_version`；
- `as_of_time`；
- `environment`；
- `config_hash`；
- `user_id`，未来多用户时；
- `duration_ms`；
- 异常堆栈。

日志不得包含账户密钥、Token 或完整个人敏感数据。

## 7. 异常处理

- 领域错误使用明确异常类型；
- 外部服务错误包装为基础设施异常；
- 不使用裸 `except Exception: pass`；
- 数据异常默认 fail closed，不默默填值；
- UI 错误返回稳定错误码，不暴露内部堆栈；
- 定时任务失败必须可重试且具备幂等性。

## 8. 版本与发布

采用语义化版本：

- `MAJOR`：不兼容 API、数据格式或策略语义变更；
- `MINOR`：向后兼容的新功能；
- `PATCH`：修复和不改变语义的优化。

策略版本、代码版本和数据版本独立管理。一个应用版本可同时运行多个策略版本。

## 9. 质量门禁

合并到 `main` 前必须通过：

- Ruff lint 与 format；
- mypy 核心模块严格模式；
- 单元、集成和回归测试；
- 覆盖率不低于当前基线；
- 文档链接检查；
- 依赖安全扫描；
- 关键回测 golden file 回归；
- 对架构边界的 import 检查。

## 10. 技术债管理

技术债必须进入 Issue，不使用永久 TODO。每项技术债记录：

- 产生原因；
- 影响范围；
- 风险等级；
- 预计偿还 Milestone；
- 临时保护措施。

## 11. Definition of Done

一个功能只有在以下条件全部满足时才算完成：

- 业务行为有明确验收标准；
- 接口和数据结构已文档化；
- 正常、边界和失败路径有测试；
- 日志和指标可观察；
- 配置可复现；
- 不破坏架构边界；
- 更新相关文档和 ADR；
- CI 全绿。

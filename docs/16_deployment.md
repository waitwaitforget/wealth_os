# 16. 部署设计

## 1. 环境

建议至少三套：

- `local`：开发和研究；
- `staging`：真实数据、模拟账户、接近生产配置；
- `production`：正式只读或小资金环境。

配置、凭证、数据库和数据目录必须隔离。

## 2. 本地优先

早期优先支持单机运行：

- Python 服务；
- DuckDB/Parquet；
- 本地或轻量 PostgreSQL；
- Next.js PWA；
- Docker Compose；
- 定时任务。

这足以支撑个人研究和移动端访问。

## 3. 容器

镜像分为：

- backend/API；
- scheduler/worker；
- web；
- docs，可选。

研究 Notebook 环境与生产执行环境分开，防止无控制依赖进入生产。

## 4. 持久化

- Raw/Canonical/Feature 使用对象存储或挂载卷；
- 元数据、任务、决策和审计使用 PostgreSQL；
- DuckDB 用于分析，不承担高并发事务；
- 备份加密。

## 5. CI/CD

PR：

- lint、type、test、coverage；
- build package；
- build docs；
- security scan。

Main：

- 构建不可变镜像；
- 发布到 staging；
- 回归和 smoke test；
- 人工批准 production；
- 保留回滚版本。

## 6. 配置与迁移

- 数据库迁移使用 Alembic；
- 配置有 schema version；
- 重大数据格式变化提供迁移脚本；
- 回滚前确认是否存在不可逆数据迁移。

## 7. 调度

首版可用 APScheduler/Prefect。选择原则：

- 单机、少任务：APScheduler；
- 需要重试、依赖图、观察和历史运行：Prefect。

不提前引入 Kubernetes。

## 8. 实盘隔离

- 实盘执行进程独立；
- 研究代码不能直接调用实盘凭证；
- 订单计划经过审批存储后由执行器消费；
- Kill switch 与部署版本无关；
- 实盘环境只能运行已批准策略版本。

## 9. 首版验收

- 一条命令启动开发环境；
- Staging 可持续更新真实数据并运行模拟组合；
- 所有镜像可重建；
- 备份和恢复测试通过；
- Production 默认不具备自动下单能力。

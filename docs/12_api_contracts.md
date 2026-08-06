# 12. API 与内部契约

## 1. 原则

API 是产品与计算内核之间的稳定边界。接口优先表达领域语义，不暴露 DataFrame、数据库表或第三方框架对象。

## 2. 版本策略

- 外部 API 使用 `/api/v1`；
- 不兼容变更发布新版本；
- 响应包含 `schema_version`；
- 内部事件也进行版本化；
- 弃用字段至少保留一个发布周期。

## 3. 核心资源

- Instruments；
- Market Data Status；
- Strategy Versions；
- Portfolio Snapshot；
- Decisions；
- Orders and Fills；
- Backtest Runs；
- Validation Reports；
- Scenarios；
- Contributions；
- Benchmarks。

## 4. 示例端点

```text
GET  /api/v1/portfolio/current
GET  /api/v1/portfolio/history
GET  /api/v1/decisions/latest
POST /api/v1/backtests
GET  /api/v1/backtests/{run_id}
GET  /api/v1/validation/{run_id}
POST /api/v1/scenarios
POST /api/v1/contributions
GET  /api/v1/market/health
```

## 5. 异步任务

回测、数据更新和模拟可能耗时，采用 Job 模型：

```text
POST request → 202 Accepted + job_id
GET /jobs/{job_id} → status/progress/result
```

任务必须支持幂等键、取消、超时和失败重试。

## 6. 标准响应

每个响应包含：

- `request_id`；
- `generated_at`；
- `as_of_time`；
- `data_version`；
- `strategy_version`；
- `schema_version`；
- `warnings`。

## 7. 错误模型

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Decision generation blocked by data validation",
    "details": [],
    "request_id": "..."
  }
}
```

错误码稳定，HTTP 状态符合语义。内部异常不直接暴露。

## 8. 金融数据表示

- 日期时间使用 ISO 8601 + 时区；
- 金额包含币种；
- 收益率和权重使用小数；
- 大数避免二进制浮点展示误差，API 金额可使用字符串或 Decimal；
- 缺失值使用 `null`，不使用 NaN；
- 指标必须标注周期和年化方法。

## 9. 内部事件

未来任务解耦可使用事件：

- `MarketDataUpdated`；
- `FactorRunCompleted`；
- `PortfolioDecisionCreated`；
- `ValidationFailed`；
- `OrderPlanApproved`；
- `ExecutionCompleted`。

第一阶段可用进程内事件总线，不需要 Kafka。

## 10. API 测试

- Schema contract tests；
- 向后兼容测试；
- 鉴权与权限；
- 幂等和重复请求；
- 任务状态机；
- 大结果分页和下载；
- 异常与超时。

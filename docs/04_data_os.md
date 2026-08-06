# 04. Data OS 设计

## 1. 目标

Data OS 为所有研究、回测和决策提供唯一可信数据源。它必须处理 A 股、港股、美股、债券、黄金、BTC、汇率、利率、估值和未来个股基本面数据，并保证时间语义、版本与来源可追溯。

## 2. 数据分层

```text
Source
  → Raw Zone
  → Staging Zone
  → Canonical Zone
  → Point-in-Time Zone
  → Feature Zone
  → Serving Cache
```

### Raw Zone

- 保存供应商原始响应；
- 不覆盖、不修正；
- 附带请求参数、状态码、校验和和抓取时间；
- 支持审计与重新处理。

### Canonical Zone

统一字段、币种、时区、复权和资产标识。转换必须确定性、版本化。

### Point-in-Time Zone

保存信息在历史时点何时可用，尤其用于估值、财报、指数成分、宏观数据和修订数据。

### Feature Zone

保存可复现特征，必须绑定代码版本、参数和输入数据版本。

## 3. Canonical Data Model

### Instrument Master

```text
instrument_id
symbol
vendor_symbols
asset_class
region
exchange
trading_calendar
quote_currency
base_currency
price_multiplier
lot_size
start_date
end_date
status
metadata_version
```

### Market Bar

```text
instrument_id
event_time
open/high/low/close
adjusted_close
volume
turnover
currency
source
revision
quality_flags
ingested_at
```

### Corporate Action

包括分红、拆股、合并、退市、基金分配和指数替换。所有总收益计算必须明确是否使用复权价格或现金流重建，禁止重复计算分红。

### FX Rate

统一约定 `base_currency/quote_currency`，记录报价方向和估值时点。组合基准币种默认 CNY。

### Valuation Observation

```text
instrument_id
metric            # pe_ttm, pb, dividend_yield, cape, erp...
value
period_end
announced_at
effective_time
source
revision
```

## 4. 时间与交易日历

系统至少区分：

- 事件发生时间；
- 数据生效时间；
- 数据对用户可见时间；
- 数据抓取时间；
- 组合估值时间；
- 订单决策时间；
- 订单可执行时间。

跨市场建议以 UTC 存储，以用户时区展示。每日组合估值需要定义统一 cut-off，不能简单将不同市场“同一日期”的收盘价视为同时可知。

BTC 24×7 交易，股票有休市。周末组合估值可以更新 BTC，但不能产生股票成交。前向填充只允许用于估值展示，不允许生成可交易信号，除非规则明确。

## 5. 数据源策略

### 原型阶段

- 免费数据源用于开发和交叉核对；
- 任何单一免费源不得直接成为实盘唯一来源；
- 所有下载结果落地并缓存。

### 稳定阶段

- 每类关键数据至少一个主源和一个校验源；
- 主源切换通过 Provider 配置，不修改业务代码；
- 记录供应商许可和再分发限制。

## 6. 数据质量规则

### 基础规则

- 主键唯一；
- 时间单调；
- OHLC 关系合法；
- 价格和汇率为正；
- 成交量非负；
- 缺失率、跳变和陈旧数据监控；
- 交易日与日历一致。

### 交叉源规则

对关键收盘价、汇率和指数值进行双源差异检查。差异超过动态阈值时进入隔离区，不能自动进入正式特征。

### 经济规则

- 总收益与价格收益差异应能由分红解释；
- ETF 与跟踪指数长期差异应落在合理范围；
- 汇率三角关系不得明显破坏；
- 财务指标必须在公告后生效。

## 7. 缺失数据策略

每个字段定义允许的缺失处理：

- `error`：关键价格缺失，任务失败；
- `stale_for_valuation`：仅用于估值展示；
- `drop_asset`：Universe 中临时剔除；
- `impute`：仅在经过验证的特征中使用；
- `manual_review`：进入人工检查。

禁止全局 `ffill()`。

## 8. 数据版本

推荐内容寻址：

```text
data_version = hash(source_files + transform_version + parameters)
```

每次回测保存：

- 输入数据版本；
- Universe 版本；
- 交易日历版本；
- 汇率版本；
- 特征版本。

## 9. 数据更新任务

- 日频行情：每个市场收盘后更新；
- BTC：按日或小时聚合；
- 估值：日频或周频；
- 宏观和利率：按发布日；
- 指数成分：按生效日；
- 数据修订：定期回查但保留历史版本。

任务必须幂等，可从断点重跑。

## 10. 验收标准

Data OS P1 完成需满足：

- 至少覆盖 8–12 个首批资产和 CNY/USD/HKD 汇率；
- 真实数据可重现下载和处理；
- 双源检查覆盖核心字段；
- 跨市场时区测试通过；
- 数据版本写入回测结果；
- 数据健康报告可自动生成。

# Wealth OS — 大盘指数估值与基本面数据系统开发说明

> **文档用途**
>
> 本文档用于指导其他开发 Agent 实现 Wealth OS 中的大盘指数估值与基本面数据模块。
>
> 目标不是简单抓取 PE/PB 字段，而是建立一套可复现、可追踪、可校验、支持 Point-in-Time，并能长期扩展到 A 股、港股、美股和行业指数的数据基础设施。

---

# 1. 背景与目标

Wealth OS 的 Core 组合需要对 A 股、港股、美股等大盘宽基指数进行：

- 价值评估
- 基本面质量评估
- 长期预期收益评估
- 历史估值分位评估
- 跨市场比较
- 调仓决策支持

系统需要稳定获取或计算以下指标。

## 1.1 核心估值指标

- PE Static
- PE TTM
- Forward PE（后续）
- PB
- PS TTM
- Dividend Yield
- Earnings Yield
- Equity Risk Premium
- Free Cash Flow Yield（后续）
- CAPE 或长期平滑盈利估值（后续）

## 1.2 核心基本面指标

- ROE
- Revenue Growth
- Earnings Growth
- Net Margin
- Operating Margin
- Profitable Constituent Weight
- Negative Earnings Weight
- Index Concentration
- Top 10 Weight
- Sector Concentration
- Financial Sector Weight
- Technology Sector Weight
- Index Market Cap

## 1.3 数据质量指标

每个指数估值快照必须同时记录：

- 有效成分覆盖率
- 缺失财务数据权重
- 亏损成分权重
- 成分数量
- 实际参与聚合的成分数量
- 数据源
- 聚合方法
- 数据版本
- 有效时间
- 抓取时间
- 可信度等级

---

# 2. 总体实现原则

## 2.1 双链路设计

系统必须同时支持两条数据链路。

### 链路 A：官方或第三方指数层数据

直接获取：

- 指数 PE
- PB
- 股息率
- 当前成分
- 当前权重
- 指数 Factsheet
- 指数编制方法

用途：

- 当前截面展示
- 官方口径锚定
- 数据交叉校验
- UI 展示
- 对自算结果进行误差分析

### 链路 B：成分股聚合计算

通过：

- 历史指数成分
- 历史权重
- 成分股 Point-in-Time 财务数据
- 历史价格
- 股本与市值

自行聚合指数估值和基本面。

用途：

- 历史回测
- 长期估值分位
- 指标扩展
- 方法透明
- 多市场统一口径
- 可复现研究

## 2.2 系统定位

```text
官方快照：用于锚定和校验
自建聚合：用于历史研究和正式回测
多源对账：用于发现口径或数据错误
```

## 2.3 禁止事项

- 不得只依赖网页展示值进行长期回测
- 不得将当前成分股回填到历史
- 不得使用财报报告期替代实际披露日
- 不得简单对成分股 PE 做加权平均
- 不得静默修正或覆盖历史数据
- 不得把 ETF 指标无条件等同于指数指标
- 不得用未来已知成分或财务数据回算历史估值
- 不得把抓取失败的数据默认填 0

---

# 3. 数据源优先级

```text
1. 指数公司官方数据
2. 交易所与监管披露
3. 专业结构化 API
4. ETF 管理人
5. 聚合型开源接口
6. 普通财经网站抓取
```

---

# 4. A 股数据源

## 4.1 主数据源：Tushare Pro

优先使用以下接口或等价能力：

- `index_dailybasic`
- `index_weight`
- `daily_basic`
- `fina_indicator`
- 资产负债表
- 利润表
- 现金流量表
- 财务披露日期
- 指数日线与总收益数据

主要用途：

- 指数历史 PE/PB
- 历史指数成分和权重
- 成分股历史市值
- 成分股 TTM 财务数据
- 自行聚合指数估值
- A 股 Point-in-Time 数据体系

## 4.2 官方校验源

### 中证指数公司

获取：

- 指数 Factsheet
- 当前 PE/PB/股息率
- 成分数量
- 前十大成分
- 行业权重
- 指数编制方法
- 指数调整规则

### 上交所、深交所

用途：

- 上市公司公告
- 公司行为
- 指数或 ETF 产品资料
- 交易日历校验

### 巨潮资讯

用途：

- 定期报告
- 财务公告
- 分红公告
- 实际披露时间核验

## 4.3 辅助校验源

- AKShare
- JoinQuant
- ETF 管理人官网
- 基金季报和组合持仓

## 4.4 首批指数

第一阶段仅实现：

```text
CSI300
CSI500
CSI_DIVIDEND
```

后续扩展：

```text
CSI1000
SSE50
CHINEXT
STAR50
```

---

# 5. 港股数据源

## 5.1 官方数据源

### 恒生指数公司

获取：

- 恒生指数
- 恒生国企指数
- 恒生科技指数
- Factsheet
- 当前 PE
- 股息率
- 波动率
- 成分和权重
- 行业结构
- 指数方法论

### HKEXnews

用途：

- 年报
- 中报
- 业绩公告
- 股息公告
- 公司行为
- 实际披露时间

## 5.2 ETF 管理人

用于：

- 当前持仓
- 当前组合估值
- 行业权重
- 前十大持仓
- 可交易产品与理论指数差异

## 5.3 港股风险

- 财务报表币种不统一
- H 股、红筹、二次上市公司口径不同
- 免费历史成分数据质量有限
- PDF 财报解析成本高
- Forward PE 通常需要商业数据源

## 5.4 首批港股指数

```text
HSI
HSCEI
HSTECH
```

## 5.5 首版策略

港股首版优先采用：

```text
官方当前估值快照
+
历史价格和趋势
+
有限历史估值数据
```

若历史估值质量无法保证，不得使用低质量数据强行完成长期回测。

---

# 6. 美股数据源

## 6.1 SEC EDGAR

优先使用：

- Company Facts API
- XBRL Frames API
- 公司 10-K / 10-Q
- 实际 filing date
- 标准化财务标签

用途：

- 收入
- 净利润
- 净资产
- 经营现金流
- 股本
- 财务披露时间
- Point-in-Time 财务数据

## 6.2 指数公司

### S&P Dow Jones Indices

获取：

- S&P 500 方法论
- 指数资料
- 当前估值和盈利资料
- 成分与行业信息

### Nasdaq

获取：

- Nasdaq-100 方法论
- 成分
- 指数资料
- 指数研究

## 6.3 ETF 管理人

可使用：

- SPY
- IVV
- VOO
- QQQ

获取：

- 当前持仓
- 权重
- P/E
- P/B
- ROE
- 行业分布
- 前十大持仓

ETF 层数据只能用于当前截面、可交易产品分析和指数结果校验，不能直接替代指数历史估值。

## 6.4 首批指数

```text
SP500
NASDAQ100
```

## 6.5 首版限制

首版不强制实现：

- Forward PE
- 分析师一致预期 EPS
- 长期历史成分完整重建
- 基于分析师预测的盈利增长

---

# 7. 商业数据源

后续可评估：

- Wind
- Choice
- iFinD
- Bloomberg
- FactSet
- LSEG Workspace / Datastream
- S&P Capital IQ
- Morningstar Direct

触发采购条件：

- 港股历史基本面成为关键瓶颈
- 需要 Forward PE
- 需要完整历史指数成分
- 需要数千只股票的个股 Alpha
- 免费数据清洗成本高于订阅成本
- 实盘资金规模足以覆盖数据成本

---

# 8. 指数聚合方法

## 8.1 指数 PE

禁止使用：

```text
sum(weight_i * PE_i)
```

推荐：

```math
PE_index = sum(MarketCap_i) / sum(Earnings_i)
```

要求：

- 使用一致的市值口径
- 使用 TTM Earnings
- 亏损公司利润仍纳入总盈利
- 记录负盈利权重
- 若总盈利小于或接近 0，PE 标记为不可解释

## 8.2 指数 PB

```math
PB_index = sum(MarketCap_i) / sum(BookValue_i)
```

## 8.3 指数 PS

```math
PS_index = sum(MarketCap_i) / sum(Revenue_i)
```

## 8.4 股息率

```math
DividendYield_index = sum(Dividend_i) / sum(MarketCap_i)
```

首版仅实现 Trailing 12M。

## 8.5 ROE

```math
ROE_index = sum(NetIncome_i) / sum(AverageEquity_i)
```

## 8.6 盈利增长率

```math
EarningsGrowth = AggregateEarnings_t / AggregateEarnings_{t-1} - 1
```

必须明确是否包含成分变化影响。

## 8.7 集中度

实现：

- Top 10 Weight
- Herfindahl-Hirschman Index
- 最大单一成分权重
- 最大行业权重

---

# 9. 数据模型

## 9.1 指数基础信息

```text
index_master
├── index_id
├── index_name
├── provider
├── market
├── currency
├── base_date
├── launch_date
├── methodology_version
├── rebalance_frequency
├── source_url
├── created_at
└── updated_at
```

## 9.2 指数估值快照

```text
index_valuation_snapshot
├── index_id
├── observation_date
├── pe_static
├── pe_ttm
├── pe_forward
├── pb
├── ps_ttm
├── dividend_yield_ttm
├── earnings_yield
├── equity_risk_premium
├── roe
├── revenue_growth
├── earnings_growth
├── market_cap
├── component_count
├── valid_component_count
├── valid_weight
├── missing_weight
├── negative_earnings_weight
├── aggregation_method
├── methodology_version
├── confidence_score
├── source
├── source_data_version
├── effective_time
├── ingestion_time
└── revision_version
```

## 9.3 指数成分历史

```text
index_constituent_history
├── index_id
├── constituent_id
├── announcement_date
├── effective_date
├── end_date
├── weight
├── shares
├── free_float_factor
├── currency
├── source
├── ingestion_time
└── revision_version
```

## 9.4 成分财务快照

```text
constituent_fundamental_snapshot
├── instrument_id
├── report_period
├── filing_date
├── effective_date
├── currency
├── revenue_ttm
├── net_income_ttm
├── book_value
├── average_equity
├── operating_cash_flow_ttm
├── free_cash_flow_ttm
├── dividend_ttm
├── shares_outstanding
├── source
├── source_data_version
└── revision_version
```

## 9.5 数据质量报告

```text
index_valuation_quality_report
├── index_id
├── observation_date
├── total_component_count
├── valid_component_count
├── valid_weight
├── missing_weight
├── negative_earnings_weight
├── stale_financial_weight
├── currency_conversion_missing_weight
├── official_pe
├── calculated_pe
├── pe_relative_error
├── official_pb
├── calculated_pb
├── pb_relative_error
├── severity
├── issues
└── generated_at
```

---

# 10. 领域接口设计

## 10.1 官方指数数据 Provider

```python
class OfficialIndexDataProvider(Protocol):
    def fetch_index_snapshot(
        self,
        index_id: str,
        as_of_date: date,
    ) -> IndexValuationSnapshot:
        ...

    def fetch_constituents(
        self,
        index_id: str,
        as_of_date: date,
    ) -> list[IndexConstituent]:
        ...
```

## 10.2 成分股财务 Provider

```python
class FundamentalDataProvider(Protocol):
    def fetch_fundamentals(
        self,
        instrument_ids: list[str],
        as_of_date: date,
    ) -> list[FundamentalSnapshot]:
        ...
```

## 10.3 指数聚合器

```python
class IndexFundamentalAggregator(Protocol):
    def aggregate(
        self,
        index: IndexDefinition,
        constituents: list[IndexConstituent],
        fundamentals: list[FundamentalSnapshot],
        market_data: list[MarketSnapshot],
        fx_rates: list[FXRate],
        as_of_date: date,
    ) -> IndexValuationSnapshot:
        ...
```

## 10.4 校验器

```python
class IndexValuationValidator(Protocol):
    def validate(
        self,
        calculated: IndexValuationSnapshot,
        official: IndexValuationSnapshot | None,
    ) -> IndexValuationQualityReport:
        ...
```

---

# 11. 时间语义与 Point-in-Time

必须区分：

- `report_period`
- `announcement_date`
- `filing_date`
- `effective_date`
- `observation_date`
- `ingestion_time`
- `revision_version`

在日期 `t` 计算指数估值时：

- 只能使用 `effective_date <= t` 的成分
- 只能使用 `filing_date <= t` 的财务数据
- 只能使用 `observation_date <= t` 的市场价格
- 收盘后生成的信号不得按同一收盘价成交
- 财务数据修订必须创建新版本，不能覆盖旧版本
- 成分切换使用调整生效日，不能使用公告日提前替换

---

# 12. 汇率与币种处理

- Wealth OS 默认以人民币作为总组合基准币种
- 聚合前应将市值、收入、盈利、净资产和股息转换到同一币种
- 首批支持 USD/CNY、HKD/CNY
- 汇率缺失时不得默认使用 1
- 必须记录缺失币种权重、最近可用汇率日期和汇率是否过期

---

# 13. 数据质量规则

## 13.1 覆盖率

```text
valid_weight >= 98%        PASS
95% <= valid_weight < 98%  WARNING
valid_weight < 95%         FAIL
```

## 13.2 官方值误差

建议首版：

```text
PE relative error <= 3%       PASS
3% < error <= 8%              WARNING
error > 8%                    FAIL
```

PB、股息率可设置独立阈值。

## 13.3 异常规则

- 总盈利接近 0 时 PE 不可解释
- 负盈利权重超过阈值需降置信度
- 财务数据过旧需告警
- 成分权重不足 100% 需解释
- 单一成分权重大幅变化需告警
- 官方值与自算值持续偏离需阻断下游因子

---

# 14. 置信度评分

建议初版：

```text
confidence_score =
    coverage_score
  × freshness_score
  × source_score
  × reconciliation_score
```

等级：

```text
A：>= 0.90
B：0.80–0.90
C：0.65–0.80
D：< 0.65
```

下游规则：

- A / B：允许进入正式估值因子
- C：仅展示，不用于自动调仓
- D：阻断策略输入

---

# 15. 实现目录建议

```text
src/wealth_os/
├── domain/
│   ├── index.py
│   ├── valuation.py
│   ├── fundamentals.py
│   └── data_quality.py
├── application/
│   ├── build_index_snapshot.py
│   ├── refresh_index_data.py
│   └── validate_index_valuation.py
├── infrastructure/
│   ├── providers/
│   │   ├── tushare/
│   │   ├── csindex/
│   │   ├── hang_seng/
│   │   ├── sec/
│   │   ├── yahoo/
│   │   └── etf_managers/
│   ├── repositories/
│   │   ├── parquet_index_repository.py
│   │   └── duckdb_index_repository.py
│   └── parsers/
│       ├── factsheet_parser.py
│       └── xbrl_mapper.py
├── research/
│   ├── index_aggregation/
│   │   ├── pe.py
│   │   ├── pb.py
│   │   ├── dividend_yield.py
│   │   ├── roe.py
│   │   └── concentration.py
│   └── valuation/
│       ├── percentile.py
│       └── expected_return.py
└── validation/
    ├── index_data_checks.py
    ├── point_in_time_checks.py
    └── reconciliation.py
```

---

# 16. 第一阶段开发任务

## Sprint A：领域模型

- [ ] `IndexDefinition`
- [ ] `IndexConstituent`
- [ ] `IndexValuationSnapshot`
- [ ] `FundamentalSnapshot`
- [ ] `IndexValuationQualityReport`
- [ ] Provider Protocol
- [ ] Repository Protocol

## Sprint B：A 股直接估值链路

- [ ] 接入 Tushare `index_dailybasic`
- [ ] 支持 CSI300
- [ ] 支持 CSI500
- [ ] 支持中证红利
- [ ] 落库 Parquet
- [ ] 建立 DuckDB View
- [ ] 实现增量更新
- [ ] 实现数据版本记录

## Sprint C：A 股成分聚合链路

- [ ] 接入 `index_weight`
- [ ] 接入个股 `daily_basic`
- [ ] 接入财务数据
- [ ] 使用实际披露日
- [ ] 聚合 PE
- [ ] 聚合 PB
- [ ] 聚合股息率
- [ ] 聚合 ROE
- [ ] 计算覆盖率和亏损权重

## Sprint D：官方校验

- [ ] 存档中证指数 Factsheet
- [ ] 解析官方 PE/PB/股息率
- [ ] 自算值与官方值对账
- [ ] 生成差异报告
- [ ] 建立阈值和告警

## Sprint E：历史估值序列

- [ ] 建立日频或周频快照
- [ ] 计算历史分位
- [ ] 计算滚动 5/10/15 年分位
- [ ] 输出数据可信度
- [ ] 接入现有 Value Factor

---

# 17. 第二阶段扩展

## 港股

- [ ] 恒生指数 Factsheet Provider
- [ ] HSI / HSCEI / HSTECH
- [ ] 港股成分和权重
- [ ] 财报币种归一
- [ ] HKEXnews 校验
- [ ] ETF 持仓校验

## 美股

- [ ] SEC Company Facts Provider
- [ ] XBRL 字段映射
- [ ] SP500 / NASDAQ100
- [ ] ETF 当前持仓
- [ ] S&P / Nasdaq 官方快照
- [ ] 美股指数聚合估值
- [ ] 美元到人民币换算

---

# 18. 测试要求

## 18.1 单元测试

必须覆盖：

- PE 聚合
- PB 聚合
- 股息率
- ROE
- 亏损公司
- 缺失成分
- 汇率转换
- 成分生效日
- 财务披露日
- 负总盈利
- 权重不满 100%

## 18.2 手算样例

构造 3–5 只股票的小型指数，人工计算：

- 市值
- 盈利
- PE
- PB
- 股息率
- ROE

代码结果必须与手算一致。

## 18.3 Point-in-Time 测试

- 删除未来财务数据后，历史结果不变
- 修改未来成分后，历史结果不变
- 财报披露前不得使用该财报
- 调仓生效前不得使用新成分

## 18.4 回归测试

固定日期和固定数据版本保存 Golden Snapshot。

以下变化必须人工审查：

- PE
- PB
- 股息率
- 成分数量
- 覆盖率
- 官方误差

---

# 19. 日志与审计

每次运行记录：

```text
run_id
index_id
as_of_date
provider
source_data_version
constituent_version
fundamental_version
fx_version
aggregation_method
code_version
quality_result
output_path
```

任何结果都必须追溯到原始数据、数据版本、聚合方法、代码版本和配置版本。

---

# 20. CLI 建议

```bash
wealth-os index refresh --index CSI300 --start 2015-01-01
wealth-os index snapshot --index CSI300 --date 2026-08-01
wealth-os index validate --index CSI300 --date 2026-08-01
wealth-os index reconcile --index CSI300 --date 2026-08-01
wealth-os index history --index CSI300 --metric pe_ttm
wealth-os index health --index CSI300
```

---

# 21. 输出示例

```text
Index: CSI300
Date: 2026-08-01

PE TTM: 12.84
PB: 1.31
Dividend Yield: 3.12%
ROE: 10.87%
Earnings Growth: 4.60%

Valid Weight: 99.21%
Negative Earnings Weight: 2.87%
Missing Weight: 0.79%

Official PE: 12.91
Calculated PE: 12.84
Relative Error: -0.54%

Confidence: A
Data Version: csi300-20260801-v3
```

---

# 22. 验收标准

第一阶段必须满足：

- [ ] 支持 CSI300、CSI500、中证红利
- [ ] 可获取指数直接估值
- [ ] 可获取历史成分和权重
- [ ] 可自行聚合 PE/PB/股息率
- [ ] 财务数据使用实际披露时间
- [ ] 可固定数据版本复现
- [ ] 可输出覆盖率和亏损权重
- [ ] 可与官方值对账
- [ ] 差异超过阈值自动告警
- [ ] 有完整单元测试和手算样例
- [ ] 有 CLI 和文档
- [ ] 可接入现有 Value Factor
- [ ] 真实数据与 Demo 数据明确区分

---

# 23. 非目标

当前阶段不实现：

- Forward PE
- 分析师一致预期
- 高频估值更新
- 个股 Alpha
- 自动实盘
- 复杂 PDF OCR
- 港股全市场财务标准化
- 美股全部历史指数成分
- 深度学习估值模型

---

# 24. Agent 执行顺序

```text
1. 领域模型与接口
2. Tushare 指数直接估值
3. Parquet + DuckDB 落库
4. 历史成分和权重
5. 个股财务 Point-in-Time
6. 指数聚合器
7. 官方 Factsheet 校验
8. 数据质量报告
9. 历史估值序列
10. 接入 Value Factor
```

不要先实现 UI，不要先优化策略收益。

---

# 25. 最终原则

指数估值系统的第一目标不是“多拿几个指标”，而是保证每一个指标都能回答：

- 它来自哪里？
- 它如何计算？
- 使用了哪些成分？
- 使用了哪一期财务数据？
- 当时市场是否已经知道这些数据？
- 与官方口径为什么一致或不一致？
- 这个结果是否足以用于自动调仓？

只有满足这些要求，指数估值数据才能进入 Wealth OS 的正式投资决策链路。

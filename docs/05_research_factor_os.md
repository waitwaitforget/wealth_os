# 05. Research & Factor OS 设计

## 1. 目标

Research OS 将原始数据转为可验证的特征、因子和模型输出。它同时服务低频宽基配置、行业轮动和未来个股 Alpha，但不同策略的标签、频率和评价标准必须隔离。

## 2. 概念分层

- **Feature**：直接由数据计算的观测量，例如 12 月动量、60 日波动率；
- **Factor**：具有经济含义且经过标准化的信号，例如趋势分数；
- **Model Output**：规则或模型对收益、风险、状态的预测；
- **Allocation Input**：Portfolio Engine 实际消费的稳定接口。

禁止将未经校验的原始特征直接映射为仓位。

## 3. Core 因子体系

### 3.1 Value

适用于股票宽基，候选指标包括：

- Earnings Yield；
- Book-to-Price；
- Dividend Yield；
- CAPE 或平滑盈利收益率；
- Equity Risk Premium；
- 现金流收益率，数据可用时。

处理原则：

- 在各市场自身历史中标准化；
- 同时保留绝对值、历史分位和横截面分位；
- 使用多个窗口避免起点敏感；
- 价值只用于长期收益中枢和倾斜，不直接做短期止损。

### 3.2 Trend

候选特征：

- 3、6、12 月总收益；
- 12–1 月动量；
- 200 日或 10 月均线状态；
- 均线斜率；
- 距离历史高点；
- 多周期共识。

趋势输出应连续化，并设置滞后和跨档触发，避免单点噪声导致频繁交易。

### 3.3 Risk

- 多窗口实现波动率；
- 下行波动率；
- 最大回撤与 Ulcer Index；
- Expected Shortfall；
- 跳跃和偏度；
- 滚动相关性和相关性聚类；
- 流动性代理。

风险因子优先作用于仓位上限和组合缩放，而不是预测收益。

### 3.4 Macro 与 Liquidity

首版不作为主因子，可作为解释或风险状态输入。使用时必须处理发布滞后和数据修订。

## 4. BTC 因子

BTC 不使用 PE、PB 等传统估值。首版采用：

- 多周期趋势；
- 实现与下行波动率；
- 回撤状态；
- 与股票的滚动相关性；
- 适度的长期偏离或链上指标，后续验证后加入。

BTC 仓位受硬上限和风险贡献约束。

## 5. Satellite 因子

### 行业阶段

- 动量与相对强弱；
- 估值；
- 盈利修正；
- 景气和资金流；
- 质量；
- 波动和拥挤度。

### 个股阶段

需要加入：

- 去极值、标准化；
- 行业和市值中性化；
- Point-in-Time 基本面；
- Rank IC、ICIR 和分层收益；
- 风格暴露和交易成本后 Alpha。

Qlib 在这一阶段作为训练和实验工作流，而不是组合权重的唯一来源。

## 6. 因子接口与元数据

```python
@dataclass(frozen=True)
class FactorSpec:
    factor_id: str
    version: str
    frequency: str
    required_fields: tuple[str, ...]
    lookback: int
    publication_lag: int
    normalization: str
    missing_policy: str


class FactorModel(Protocol):
    def compute(self, context: FactorContext) -> FactorResult: ...
```

每个 FactorResult 记录：

- as-of 时间；
- 输入数据版本；
- 参数；
- 有效 Universe；
- 缺失和质量标记；
- 计算耗时。

## 7. 因子验证

每个因子必须通过：

1. 手工小样本单元测试；
2. 无未来信息测试；
3. 单调性和边界测试；
4. 数据缺失和异常测试；
5. 参数邻域稳定性；
6. 不同市场与阶段表现；
7. 经济含义检查；
8. 成本后增量贡献。

## 8. 实验管理

每次实验记录：

- Git commit；
- 数据和特征版本；
- 配置；
- 随机种子；
- 训练/验证/测试区间；
- 所有尝试而非仅最佳结果；
- 指标、图表和模型文件；
- 结论与失败原因。

## 9. 防止过拟合

- 参数数量与样本长度匹配；
- 使用 Walk-forward；
- 多起点和多市场验证；
- 记录试验次数；
- 优先选择参数平台而非尖峰；
- 使用消融和延迟扰动；
- 不以单一 Sharpe 排名选模型；
- 结果必须对成本和执行延迟稳健。

## 10. 首版验收

- Value、Trend、Risk 均有版本化实现；
- 每个因子有元数据、单测和无未来信息测试；
- 可生成因子健康报告；
- 能完成 V/T/R 消融；
- 因子输出与 Portfolio Engine 完全解耦。

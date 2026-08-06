# 10. Decision Engine 设计

## 1. 目标

Decision Engine 将因子、组合优化和风险覆盖转化为用户可理解、可执行、可追溯的建议。它不是自然语言包装器，而是结构化决策对象的生成器。

## 2. 决策对象

```python
@dataclass(frozen=True)
class PortfolioDecision:
    decision_id: str
    as_of_time: datetime
    current_weights: Mapping[str, float]
    theoretical_weights: Mapping[str, float]
    risk_adjusted_weights: Mapping[str, float]
    executable_weights: Mapping[str, float]
    actions: tuple[AssetAction, ...]
    triggers: tuple[TriggerReason, ...]
    confidence: ConfidenceAssessment
    risks: tuple[RiskNotice, ...]
    versions: DecisionVersions
```

每个 AssetAction 包括：

- 当前、目标和变化权重；
- 买、卖、持有或转现金；
- Value、Trend、Risk、Correlation、Currency 和 Constraint 的贡献；
- 预计金额、费用和执行时间；
- 不执行时的风险；
- 置信度和不确定性。

## 3. 解释原则

- 解释必须由结构化贡献生成；
- 不使用事后编造的理由；
- 区分资产自身评分与组合边际效用；
- 明确哪些是模型结论、哪些是硬约束；
- 对不确定结果使用区间和等级；
- 不输出收益承诺。

## 4. 决策类型

- No Action；
- Deploy Cash；
- Increase Exposure；
- Reduce Exposure；
- Rebalance Drift；
- Risk Override；
- Strategy Budget Change；
- Data/Validation Hold；
- Manual Review Required。

Validation FAIL 时，Decision Engine 默认输出 `Data/Validation Hold`，禁止产生正常交易建议。

## 5. 触发与冷却

决策生成和实际交易分离。系统可每日更新目标，但只有满足触发条件才生成可执行动作。

降风险动作可以立即执行；增加风险需要冷却、信号确认和成本收益阈值。

## 6. 置信度

置信度不是预测准确率，而是综合：

- 数据质量；
- 因子一致性；
- 参数稳定性；
- 样本外支持；
- 当前市场是否超出训练/历史分布；
- 多模型或多周期共识；
- 执行可行性。

输出高/中/低等级和构成，不只给一个百分数。

## 7. 决策日志

每次建议保存：

- 输入数据快照；
- 信号和风险状态；
- 所有层次权重；
- 触发原因；
- 建议订单；
- 用户是否执行；
- 人工覆盖原因；
- 后续结果与反事实结果。

## 8. 人工覆盖

系统必须允许：

- 暂停某资产交易；
- 限制某币种换汇；
- 延迟执行；
- 修改最大金额；
- 拒绝建议。

人工覆盖不应修改策略历史，应作为单独执行层记录。

## 9. 通知策略

只对真正需要动作或风险异常的事件通知：

- 风险状态升级；
- 权重偏离达到阈值；
- 新增资金有明确部署建议；
- 数据或校验失败；
- 策略进入审查；
- 订单执行偏差。

避免每日无意义推送。

## 10. 首版验收

- 决策有稳定 JSON Schema；
- 每个权重变化都有贡献解释；
- Validation 可以阻断决策；
- No Action 也有明确原因；
- 决策与订单、成交和实际结果可关联；
- UI 不需要重新推断业务逻辑。

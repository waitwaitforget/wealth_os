# 09. Validation & Governance 系统

## 1. 定位

Validation 不是测试目录中的几个断言，而是独立的产品能力。它回答：数据是否可信、因子是否正确、回测是否存在未来信息、账户是否守恒、策略是否稳健、实盘是否偏离模型。

## 2. 分层质量闸门

```text
Data Gate
  → Feature/Factor Gate
  → Portfolio Gate
  → Accounting Gate
  → Backtest Gate
  → Statistical Gate
  → Shadow/Live Gate
  → Release Gate
```

任一 Error 级别问题默认阻止正式结果发布。

## 3. 数据校验

- Schema、类型、主键和时间顺序；
- 价格、OHLC、成交量和汇率范围；
- 缺失、陈旧和异常跳变；
- 交易日历一致性；
- 多源对比；
- 复权、分红和总收益一致；
- Point-in-Time 和公告滞后；
- 数据版本和校验和。

## 4. 因子校验

- 手工可计算的小样本；
- 单调性和方向性；
- 参数边界；
- 缺失数据；
- 未来数据破坏测试；
- 延迟一到数日扰动；
- 因子分布漂移；
- 不同市场与时间段稳定性。

## 5. 组合校验

不变量：

- 权重和为 1；
- 无杠杆时非负；
- 现金、资产、Sleeve、币种和风险上下限；
- 换手上限；
- 输入信号极端时仍有合法解；
- 初始部署阶段与正常阶段约束分离；
- 目标权重变化符合解释。

建议使用 Hypothesis 生成随机市场状态做属性测试。

## 6. 会计校验

每日必须满足：

```text
NAV = cash + positions
ΔNAV = market PnL + external flow - costs
unit_nav = NAV / units
```

还需验证：

- 入金只增加份额；
- 提现只减少份额；
- 订单资金守恒；
- 多币种转换前后守恒；
- 成本不会被重复扣除；
- 期末财富 = 累计净投入 + 投资损益。

## 7. 回测语义校验

- 信号与成交时间顺序；
- 休市和停牌不可成交；
- 下一个可交易价格；
- 不同引擎逐日一致；
- 交易成本和税费方向正确；
- 持仓数量和权重可从订单重建；
- 首日建仓成本包含在 TWR。

## 8. 统计稳健性

- Walk-forward；
- 多起点；
- 参数邻域；
- Bootstrap/block bootstrap；
- 成本和延迟压力；
- 数据扰动；
- 模块消融；
- 历史市场阶段切片；
- 多重试验记录和过拟合风险。

## 9. 基准与失效治理

### 基准

- Core：固定战略组合；
- Satellite：对应市场或行业基准；
- 总组合：同风险水平静态组合；
- Cash：对应币种现金收益。

### 策略状态

- Research；
- Candidate；
- Shadow；
- Limited Capital；
- Production；
- Review；
- Suspended；
- Retired。

状态迁移有明确指标、人工审批和版本记录。

## 10. Shadow Portfolio

至少维护：

1. 实际组合；
2. 完全按模型执行的影子组合；
3. 固定战略基准；
4. 可选的无风险覆盖组合。

归因：

```text
Actual - Benchmark = Strategy + Execution + Cost + Cash timing + Manual override
```

## 11. Health Report

每日/每次运行输出：

- 总体状态：PASS/WARN/FAIL；
- 数据健康度；
- 因子健康度；
- 组合约束；
- 会计误差；
- 引擎差异；
- 策略漂移；
- 未解决问题；
- 阻断发布的原因。

评分可用于展示，但不能掩盖 Error。一个 99 分报告只要有会计错误仍然必须 FAIL。

## 12. 发布门禁

策略或代码进入生产前：

- 所有 Error 为零；
- 核心回归结果在容差内；
- 样本外符合设计目标；
- 成本后仍有效；
- 文档、配置和 ADR 完整；
- Shadow 运行达到规定周期；
- 人工批准。

## 13. 首版验收

- ValidationReport 有稳定 Schema；
- CLI 和 API 可生成报告；
- CI 中运行基础 Gate；
- 真实数据回测绑定报告；
- Native/VectorBT 差异自动输出；
- 所有策略状态和审批可审计。

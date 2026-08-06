# 19. Git 仓库与协作治理

## 1. 分支策略

对于当前单人/少人开发，推荐轻量 trunk-based，而不是长期维护 `develop`：

- `main`：始终可发布；
- `feature/<issue>-<name>`：短生命周期功能分支；
- `fix/<issue>-<name>`；
- `release/*` 仅在确有稳定发布周期时使用；
- 紧急修复从 `main` 创建并回到 `main`。

长期 `develop` 容易造成大批量集成和分支漂移。只有团队规模和发布流程证明必要时再引入。

## 2. Commit 规范

采用 Conventional Commits：

```text
feat(data): add canonical FX model
fix(accounting): include first-day transaction cost in TWR
refactor(domain): isolate vectorbt adapter
 test(validation): add future-data corruption check
docs(architecture): document cash as first-class asset
```

提交应小而完整，避免把格式化、重构和功能混在一起。

## 3. Pull Request

每个 PR 包含：

- 背景和目标；
- 变更范围；
- 金融语义影响；
- 测试和验证；
- 回测结果是否变化；
- 数据或配置迁移；
- 风险和回滚方案；
- 相关 ADR/Issue。

## 4. 保护规则

`main`：

- 禁止直接 push；
- CI 必须通过；
- 至少一名 Reviewer，单人项目可由自检清单替代但保留 PR；
- 禁止 force push；
- 合并后删除分支；
- 使用 squash 或 rebase 保持历史清晰。

## 5. Issue 类型

- Feature；
- Bug；
- Research；
- Data Quality；
- Validation Failure；
- Architecture/ADR；
- Technical Debt；
- Security。

Issue 必须有验收标准和优先级。

## 6. 标签

建议：

- `area:data`、`area:portfolio`、`area:risk`；
- `priority:p0/p1/p2`；
- `type:bug/feature/research/debt`；
- `status:blocked/ready`；
- `risk:financial/security/data`。

## 7. Release

每次发布包含：

- Changelog；
- 代码版本；
- 数据 Schema 版本；
- 策略版本；
- 已知限制；
- 回归摘要；
- 迁移和回滚说明。

策略参数变化即使代码不变，也需要新的策略版本和变更记录。

## 8. 大文件与数据

- 市场数据、模型和回测 artifact 不进入普通 Git；
- 必要时使用对象存储、DVC 或 Git LFS；
- 小型 fixtures 可提交；
- `.gitignore` 排除缓存、密钥、数据库、Notebook 输出和本地数据。

## 9. CODEOWNERS

按模块指定 Reviewer。单人阶段可以由未来角色占位：

```text
/src/wealth_os/accounting/  @owner
/src/wealth_os/risk/        @owner
/docs/adr/                  @owner
```

Accounting、Risk、Execution 和 Security 的改动始终视为高风险。

## 10. ADR 触发条件

以下变化需要 ADR：

- 架构风格；
- 数据格式和时间语义；
- 回测成交顺序；
- 收益口径；
- 风险和资金治理；
- 第三方核心框架；
- 实盘权限和安全。

## 11. Codex 开发建议

每次让 Codex 开发前提供：

- 对应 Issue；
- 相关设计文档；
- 明确验收标准；
- 不允许修改的架构边界；
- 必须运行的测试命令。

要求 Codex 先读文档和现有测试，再提交小 PR，避免一次性重写全仓库。

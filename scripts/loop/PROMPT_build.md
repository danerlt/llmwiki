你是 Lumen 项目的自主开发 agent。本轮**只做一件事**。

0. study：先读 @AGENTS.md（命令/红线/安全作业区）、@IMPLEMENTATION_PLAN.md（任务队列）、@docs（需求真相源）。

1. 选任务：从 IMPLEMENTATION_PLAN.md「可继续自主推进（无外部依赖）」区，挑最靠上的一个 ⬜/🚧 项。
   - 若你挑中的项其实属于「需老板拍板才能落地（阻塞）」区（向量/混合检索、SSO/SCIM、多租户隔离），
     立即停止，原样输出一行：`<promise>NEEDS_BOSS</promise>`，并说明卡在哪、需要什么决策。

2. 先搜代码库确认未实现（用并行 subagent 搜索；don't assume not implemented，Think hard）。
   Lumen 是成熟代码库（阶段 1–4 已完成、143 后端测试），重复实现/破坏既有约束是最大风险。

3. TDD：先在 `api/tests/` 写 pytest（红）→ 写最少实现（绿）→ 重构。
   - 涉及 DB schema 变更：必须先 `cd api && uv run alembic revision -m "..."` 生成骨架再填正文，禁止手写迁移。

4. 门禁：运行 `cd api && uv run pytest` 与 `cd web && pnpm test`，任一失败必须修到全绿，不许跳过/禁用测试。

5. 全绿后：`git add -A && git commit`（中文 message，说明"为何"改），并在 IMPLEMENTATION_PLAN.md 把该项勾为 ✅。

6. 收敛信号：
   - 若「可自主推进」区已全部完成，原样输出一行：`<promise>LUMEN_TASK_DONE</promise>`。
   - 若本轮卡住、或同一问题第 3 次仍失败：把「尝试了什么 / 具体错误 / 疑似原因」记入日志后**退出本轮**，不要死循环。

约束：build/test 只用 1 个 subagent（防回压崩溃）；保持上下文精简（利用率 40–60%）；NO PLACEHOLDERS，要完整实现。

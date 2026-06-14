# Lumen 文档体系（superpowers）

本目录用 [superpowers](https://github.com/) 方法论沉淀 Lumen（企业级 LLM-Wiki）的设计与实现脉络。两类文档各司其职：

- **`specs/`** — 设计文档（spec）。说明「为什么这么建、范围、关键取舍、已知边界」。
- **`plans/`** — 逐任务实现计划（plan）。把一份 spec 拆成可勾选、可 TDD 执行的任务清单（`- [ ]`，先红后绿再提交）。

> 命名约定：所有文档以 `YYYY-MM-DD-<主题>.md` 命名，便于按时间线检索。

---

## 一、MVP 设计与子计划（阶段 1，doc-first 范式）

MVP 严格遵循「先 spec → 再 plan → TDD 实现」流程，是后续一切阶段的地基。

### MVP 设计 spec（1 份）

- [`specs/2026-06-13-enterprise-llm-wiki-mvp-design.md`](specs/2026-06-13-enterprise-llm-wiki-mvp-design.md)
  — 基于 Karpathy 的 LLM-Wiki 模式：LLM 把知识**增量编译成带交叉引用的结构化 wiki 页**，查询沿 index 目录 / `[[wikilink]]` / 关键词导航，**反 RAG / 反向量**。定义核心闭环（上传源 → arq worker 两步 LLM 摄入 → 带溯源 wiki 页 → 权限感知检索问答）与四级权限隔离（company / department / team / personal）。Controller–Service–Repository 分层。

### MVP 实现子计划（8 份）

| # | 计划文档 | 一句话 |
|---|---------|--------|
| 1 | [`plans/2026-06-13-mvp-plan-01-infra-skeleton.md`](plans/2026-06-13-mvp-plan-01-infra-skeleton.md) | 基础设施 + 后端骨架：FastAPI 分层 + docker-compose（PG/Redis/MinIO）+ Alembic 基线，`/api/health` 跑通。 |
| 2 | [`plans/2026-06-13-mvp-plan-02-auth-org-permissions.md`](plans/2026-06-13-mvp-plan-02-auth-org-permissions.md) | 认证·组织·权限：JWT 登录 + 部门树/团队/用户 + 四类 KB + `permission_service`，TDD 锁死权限隔离不变量。 |
| 3 | [`plans/2026-06-13-mvp-plan-03-sources-ingest.md`](plans/2026-06-13-mvp-plan-03-sources-ingest.md) | 源上传 + 确定性摄入管线：上传 → 入队 → worker 两步 LLM → 带溯源与 `[[wikilink]]` 的 wiki 页 + 链接图 + index 目录。 |
| 4 | [`plans/2026-06-13-mvp-plan-04-retrieval-query.md`](plans/2026-06-13-mvp-plan-04-retrieval-query.md) | 检索与问答：关键词召回（可移植 LIKE + PG trgm 索引）+ 图扩展 + 目录，严格按可见 KB 过滤，组装编号上下文交 LLM 生成带引用回答。 |
| 5 | [`plans/2026-06-13-mvp-plan-05-frontend.md`](plans/2026-06-13-mvp-plan-05-frontend.md) | 前端 SPA（React + Vite + TS）：登录 → KB 列表 → wiki 浏览（markdown + wikilink 跳转）→ 上传轮询 → 搜索 → 引用式问答，nginx 托管。 |
| 6 | [`plans/2026-06-13-mvp-plan-06-admin-org-ui.md`](plans/2026-06-13-mvp-plan-06-admin-org-ui.md) | 管理员组织管理界面：补 `GET /teams`、`GET /users`，前端仅 admin 可见的建/列 部门·团队·用户·成员界面。 |
| 7 | [`plans/2026-06-13-mvp-plan-07-knowledge-promotion-review.md`](plans/2026-06-13-mvp-plan-07-knowledge-promotion-review.md) | 知识晋升 + Review 审核队列：低作用域页申请晋升到高作用域 KB，由有目标库写权限的审核者批准，形成「提交→审核→晋升」治理闭环。 |
| 8 | [`plans/2026-06-13-mvp-plan-08-audit-log.md`](plans/2026-06-13-mvp-plan-08-audit-log.md) | 审计日志 / 活动轨迹：在控制器边界、与业务变更同事务记录不可变审计事件（actor/action/target/detail），`GET /api/audit` 仅 admin。 |

---

## 二、企业演进 as-built spec（阶段 2–8，本轮新增）

> **什么是 as-built spec？** = 「竣工图」。这批能力是**先开发、后回溯补档**——spec 记录的是**实际建成**的设计与取舍（而非事前计划），所有端点、表、迁移、测试均对照当时 working tree 代码逐项核实。各文档头部都列出了关联提交哈希，可回溯到具体改动。

| 阶段 | 设计文档 | 点题 |
|------|---------|------|
| 2 平台基线与可运维性 | [`specs/2026-06-14-enterprise-phase2-platform-ops-baseline-design.md`](specs/2026-06-14-enterprise-phase2-platform-ops-baseline-design.md) | 补齐企业采购「必查项」运维地基：安全响应头 + CORS + `X-Request-ID` 贯穿 + 全局异常体 + 限流 + 深度健康检查 + Prometheus 指标 + LLM 网关重试，零额外依赖、显式可配。 |
| 3 内容创作与版本 | [`specs/2026-06-14-enterprise-phase3-authoring-versioning-design.md`](specs/2026-06-14-enterprise-phase3-authoring-versioning-design.md) | 从「只能 LLM 自动生成」到人可写：人工页 CRUD + 版本历史 / 回滚 / 行级 diff + 导出 Markdown，复用 MVP 四级权限与审计基线。 |
| 4 协作 | [`specs/2026-06-14-enterprise-phase4-collaboration-design.md`](specs/2026-06-14-enterprise-phase4-collaboration-design.md) | 把 IM 讨论沉淀回知识：页面评论 + 标签 / 收藏 + 内容认证（专家背书徽章）+ 订阅通知收件箱 + 活动流 + 认证超期进「待复审」治理闭环。 |
| 5 AI 与检索升级 | [`specs/2026-06-14-enterprise-phase5-ai-retrieval-design.md`](specs/2026-06-14-enterprise-phase5-ai-retrieval-design.md) | 问答体验对标商业 AI 助手：SSE 流式问答（边生成边显示）+ 多轮对话上下文 + 答案赞/踩反馈闭环；检索底层仍沿用 MVP 关键词 + 图扩展。 |
| 6 企业身份与数据治理 | [`specs/2026-06-14-enterprise-phase6-identity-governance-design.md`](specs/2026-06-14-enterprise-phase6-identity-governance-design.md) | 跨过身份与合规硬门槛：`token_version` 软吊销（保持 JWT 无状态）+ 自助改密 + 管理员停用 + 登录失败锁定 + refresh token 静默续期 + 审计 CSV 导出 + GDPR DSAR 个人数据导出。 |
| 7 发现、分析与体验 | [`specs/2026-06-14-enterprise-phase7-discovery-analytics-design.md`](specs/2026-06-14-enterprise-phase7-discovery-analytics-design.md) | 证明知识「被用起来 + 有 ROI」：搜索按页类型分面 + Cmd-K 全局命令面板 + admin 内容健康仪表盘（陈旧/孤儿/待复审）+ 问答满意度分析，零新增依赖、可移植 SQL。 |
| 8 外部集成 | [`specs/2026-06-14-enterprise-phase8-integrations-design.md`](specs/2026-06-14-enterprise-phase8-integrations-design.md) | 从知识孤岛变企业事件枢纽：API Key / 服务账号编程接入（`X-API-Key`，可审计可吊销，仅存 sha256）+ 出站 Webhook 事件订阅（HMAC 签名，页面更新/评论推送外部）。 |

> 旁附 [`plans/2026-06-14-backend-engineering-alignment.md`](plans/2026-06-14-backend-engineering-alignment.md)：后端工程对齐计划。

---

## 三、今后流程约定（doc-first）

as-built 是对**历史先行实现**的一次性补档。**自即日起，所有新功能一律 doc-first**，逐个推进，不再先写代码后补文档：

1. **spec（brainstorming）** — 先在 `specs/` 写设计文档，厘清意图、范围、取舍、已知边界。
2. **plan（writing-plans）** — 把 spec 拆成 `plans/` 里可勾选的逐任务实现计划。
3. **TDD 开发** — 每个代码步骤：先写失败测试（红）→ 最小实现（绿）→ 重构 → 提交并关联计划。
4. **测试验证** — 跑通 DoD（后端 pytest、前端 build/test、必要的端到端）。
5. **更新文档** — 收口后更新对应 spec/plan 状态。

一次只推进一个功能，做完一个再开下一个。

---

## 四、`IMPLEMENTATION_PLAN.md` 的角色

仓库根的 `IMPLEMENTATION_PLAN.md` 是**进行中阶段的临时追踪表**——记录当前阶段的目标、成功标准、测试与状态（未开始 / 进行中 / 已完成）。它是工作台上的便签，不是长期档案：

- 进行中：随进展实时更新各阶段状态。
- **全部阶段收口后：按规则删除该文件**，长期事实归档进本目录的 specs/plans。

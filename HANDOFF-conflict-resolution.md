# 交接文档 — 多会话/自主循环冲突处理

> 用途：老板同时开了**多个 Claude Code 对话 + 一个自主循环(scripts/loop)**对**同一工作区**并发改动并提交，产生踩踏。
> 本文档供**新开的"冲突处理"对话**使用，**自包含**（不依赖任何对话记忆）。快照时间点：提交 `c30eb86`。

---

## 0. 一句话现状

实际比想象**干净**：分支线性（无分叉）、**alembic 单头（无迁移冲突）**，只有**一块未提交的在途功能(SearchMiss)**需要处置；根因是自主循环还在跑、与交互会话共用工作区。

---

## 1. Git 事实（请先 `git fetch`/核对，下面是快照）

- 当前分支：**`auto/loop-test`**，HEAD = `c30eb86`（feat(ingest): 支持 DOCX 与 HTML 摄入）。
- 另有分支：**`master`**，HEAD = `cc4f04d`。
- 分叉关系：`auto/loop-test` = `master` **+1 个提交**（就是 `c30eb86`），**线性、无分叉**（`git rev-list --left-right --count auto/loop-test...master` = `1  0`）。
  - 含义：`master` 可直接 fast-forward 到 `c30eb86`，不会冲突。
- **Alembic：单头 `dad98f206187`**（共 21 个迁移，链式，**无多头/无冲突**）。

### 未提交的工作区改动（= 另一会话/循环的在途，**不是本会话的**）
```
 M api/app/controllers/analytics.py      # 加了 search_miss 聚合(top)
 M api/app/controllers/search.py         # 0 结果时记录 search miss
 M api/app/models/__init__.py            # 导出 SearchMiss
?? api/app/models/search_miss.py         # 新模型
?? api/app/repositories/search_miss_repo.py
?? api/tests/test_api_search_misses.py   # 4 个测试，当前可过
```
**关键缺陷**：SearchMiss 模型**没有对应的 alembic 迁移**（`grep -rl search_miss migrations/versions` 为空）。测试用内存 SQLite `create_all` 能过，但**真实 Postgres 上缺表会 500**。提交前必须补迁移（`alembic revision -m "add search_misses"` 再填 upgrade/downgrade）。

---

## 2. 三股改动来源（谁动了什么）

1. **本交互会话（已提交到 `auto/loop-test`，~130 提交，止于 `c30eb86`）**：把 LLM-Wiki 从 MVP 全面建成企业级平台。详见 `IMPLEMENTATION_PLAN.md`（每阶段勾选状态）。要点：
   - 阶段1 安全加固（13 条审计修复）/ 阶段2 平台基线（中间件/异常/健康/日志/metrics/分页/LLM网关/限流/TrustedHost）/ 阶段3 创作与版本（人工 CRUD+编辑器+版本回滚+行级diff+Markdown导出）/ 阶段4 协作（评论/标签/收藏/订阅通知/内容认证/活动流/过期复审）。
   - 阶段5 AI：SSE 流式问答、多轮对话、答案反馈、**向量/混合检索代码**（本地 sentence-transformers，默认关闭）。
   - 阶段6 身份：token_version 吊销/改密/停用启用/登录锁定/refresh token、GDPR 导出、团队只读成员 ACL。
   - 阶段7：搜索分面 + Cmd-K、分析仪表盘。 阶段8：API Key、Webhook、CI。
   - **docx/html 摄入**（`c30eb86`，本会话最后一笔）。
2. **自主循环 / 另一会话（在途未提交）**：SearchMiss（搜索无果词→知识空缺分析）。功能写好、测试可过，**缺迁移、未提交**。
3. **构建/工程化重构（已并入历史）**：迁移到 uv（`pyproject.toml`/`uv.lock`/`.python-version`）、ruff+mypy 配置、CI 改用 `uv sync --frozen + uv run ruff + pytest`、`AGENTS.md`、`docs/superpowers/specs/*`、`scripts/loop/*`。这些已在提交历史里。

---

## 3. 易冲突热点文件（多股都改过，重点核对）

- `api/app/main.py`（路由注册，多功能都往里加 include_router）
- `api/app/controllers/analytics.py`（本会话加 reindex/review_due；循环加 search_miss 聚合 —— **已在工作区合并共存**）
- `api/app/controllers/search.py`（本会话加 page_type 过滤；循环加 miss 记录 —— 已共存）
- `api/app/models/__init__.py`（每个新模型都要登记 import + `__all__`）
- `api/pyproject.toml` / `api/uv.lock`（依赖：本会话加 `python-docx`；构建重构加 uv 工具链）
- `.github/workflows/ci.yml`、`api/Dockerfile`、`web/src/pages/KbPagesPage.tsx`

---

## 4. 需要在"冲突处理"对话里做的决策与动作

1. **停掉自主循环（根因）**：`scripts/loop` 仍在 master/工作区跑且护栏失效。先停它，或挪到独立 worktree/分支，**否则边修边被再次踩踏**。
2. **处置 SearchMiss 在途块**（功能完整、测试过，建议**保留**）：
   - 补迁移：`cd api && <uv/venv> python -m alembic revision -m "add search_misses table"`，在生成文件里写 create_table/drop_table（参考 `migrations/versions/*` 里 comments/answer_feedback 等表的写法）。
   - 然后 `git add` 这 6 个文件 + 新迁移，单独提交。
3. **分支收口**：决定唯一主线。最简单：把 `master` fast-forward 到 `auto/loop-test`（`git switch master && git merge --ff-only auto/loop-test`），之后统一在 master 上走；或反之。明确后删掉临时分支，避免再分叉。
4. **验证（处置完跑全绿再收工）**：
   - 后端：`cd api && uv run ruff check . && uv run python -m pytest -q`（或 `.venv/Scripts/python.exe -m pytest -q`）。
   - 前端：`cd web && pnpm build && pnpm test`。
   - 迁移：真实 PG 上 `alembic upgrade head` 不报错。
   - 起栈：`docker compose up -d --build`，`curl localhost:8088/api/readyz` 返回 `ready:true`。

---

## 5. 已定的架构决策（老板拍板，处置时遵循）

- **向量检索 = 本地 sentence-transformers**（非外部 API）。代码已完整、**默认关闭**（`EMBEDDINGS_ENABLED=false`、optional import，测试不需 torch）。激活步骤见 `IMPLEMENTATION_PLAN.md`「向量检索激活步骤」：装 ML 依赖（`uv add sentence-transformers` 或镜像 `uv sync --extra ml`）→ 置 `EMBEDDINGS_ENABLED=true` → `POST /api/admin/embeddings/reindex` 回填。torch ~2GB，建议构建稳定后单独做。
- **单租户**企业内部署 → **多租户隔离层不做**（已从待办移除）。
- **SSO/SCIM 暂不做**（老板明示），需要时再提供企业 IdP 对接信息。

---

## 6. 环境/运行备忘

- 单元测试用内存 SQLite（`create_all`，不连真 DB/Redis）；真实集成走 Postgres(pg_trgm)。
- 端口（gitignored `.env`）：Postgres `15432`、Web `8088`。`APP_ENV` 未设→dev（弱默认凭据仅 dev/test/local 放行）。
- 工具链：**uv**（venv/依赖）、**ruff**（line-length 120，CI 会 lint）、pytest/pytest-asyncio。
- 默认账号：`admin@llmwiki.com / admin12345`。

---

## 7. 处置建议顺序（TL;DR 给冲突处理对话）

1. 停自主循环 → 2. 跑一次全量测试+ruff 看基线 → 3. 给 SearchMiss 补迁移并单独提交 → 4. `master` ff 到最新、收口分支 → 5. 全绿后 `docker compose up -d --build` + `/api/readyz` 验证 → 6. （可选）按激活步骤开启向量检索。

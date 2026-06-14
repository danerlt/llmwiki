# 阶段 7：发现、分析与体验 — as-built 设计文档

> 状态：as-built（已上线）· 日期：2026-06-14 · 方法论：superpowers（回溯补档）
> 对应 IMPLEMENTATION_PLAN 阶段 7 · 关联提交：`b0c7b0e`（搜索按页类型分面）、`a7f2b10`（Cmd-K 命令面板）、`a633f07`（内容健康 + 满意度仪表盘）、`724a4a0`（过期复审提醒进「待复审」）；铺垫提交 `cc96584`（SearchHit.snippet/matched）、`aa979a660c35`（answer_feedback 表，阶段 5）、`1aaf7f57b240`（page_certification，阶段 4 提供 verified_at/verified_by）
> 说明：本组功能先开发后补档，本 spec 记录"实际建成"的设计与取舍（非事前计划）。仅描述已上线实现，未列入的能力见第 9 节"已知限制"。

---

## 1. 背景与目标

知识平台的产品闭环在阶段 1–6 已搭好（摄入、创作、协作、检索问答、身份治理），但要让采购方相信"知识真的被用起来 + 能证明 ROI"，还缺两类能力：

1. **发现（Discovery）**——内容多了之后，纯关键词列表难以定位；需要按内容类型快速收窄结果，以及一个不离手键盘的全局跳转入口。
2. **分析（Analytics）**——管理员要能一眼看到"知识库哪里在烂"（陈旧、孤岛）以及"AI 问答到底好不好用"（满意度），把治理动作（复审/补链/重认证）变成可执行清单。

阶段 7 因此交付了三块**轻量、可移植、零新增依赖**的能力：搜索页类型分面过滤、Cmd-K 全局命令面板、管理员内容健康 + 问答满意度仪表盘。设计上刻意避免引入向量库、搜索引擎或埋点系统——全部复用既有 PostgreSQL/SQLite 可移植 SQL 与既有表，符合"架构尽量简单"的项目铁律。

---

## 2. 范围

### ✅ 已建成

- **搜索按页类型分面过滤**：`GET /api/search` 新增 `page_type` 查询参数，按 `overview/entity/concept/source_summary` 单选收窄；前端 `SearchPage` 渲染分面 chips，点击即重搜。
- **Cmd-K 全局命令面板**：`CommandPalette` 组件，`Cmd/Ctrl-K` 唤起、`Esc` 关闭，200ms 防抖调 `/search` 搜页 + 静态导航跳转，全局挂载于 `Layout`。
- **内容健康仪表盘（admin）**：陈旧页（`updated_at` 早于阈值）、孤儿页（无任何出/入链）、待复审页（认证已超期）三张治理清单，`GET /api/analytics` 一次返回。
- **问答满意度分析（admin）**：由 `answer_feedback` 表按 `vote` 聚合出 up/down 计数，前端换算满意率。

### ⬜ 明确未做（对照 IMPLEMENTATION_PLAN 阶段 7）

- 搜索分面仅"页类型"一维：**作用域 / 时间 / 知识库分面**未做；多选分面未做。
- **中文纠错 / 拼写纠正**未做（检索仍为可移植 LIKE 子串 + 中文二元组兜底）。
- 分析仅"健康 + 满意度"：**活跃用户 / 热门页 / 趋势曲线**未做；**搜索无果词（知识空缺）记录**未做（无搜索查询日志表）。
- **个性化首页 / 推荐**未做。
- **i18n 多语言**、**无障碍（a11y）**、**移动端响应式**未做。

---

## 3. 架构与关键设计决策

沿用项目既有的 **Controller–Service–Repository** 分层，三块能力的落点如下：

```
                    ┌─────────────────────────────────────────────┐
  前端 (web/src)    │  SearchPage.tsx   CommandPalette.tsx   AnalyticsPage.tsx
                    └───────┬───────────────┬───────────────────┬──┘
                            │ GET /search    │ GET /search        │ GET /analytics
                    ┌───────▼───────────────▼───────┐   ┌────────▼─────────┐
  controllers       │      search.py                │   │   analytics.py   │
                    │  (q + page_type + kb 过滤)     │   │ (require_admin)  │
                    └───────┬───────────────────────┘   └───┬──────────┬───┘
  services          │ retrieval_service.retrieve            │          │
                    │ (权限感知召回 + 图扩展 + snippet)      │          │
  repositories      └────── wiki_repo.search_pages ─────────┘          │
                           wiki_repo.stale_pages / orphan_pages / review_due_pages
                           feedback_repo.counts
  models                   WikiPage (page_type/updated_at/verified_at) · PageLink · AnswerFeedback
```

### 关键设计决策

**(1) 分面在 controller 层用 Python 列表推导过滤，而非下推到 SQL。**
`controllers/search.py` 拿到 `retrieval_service.retrieve()` 返回的页集合后，在内存中按 `p.page_type == page_type` 过滤，同时硬性排除 `page_type == "index"`（目录页不进搜索结果）。
取舍理由：检索结果已被服务层 cap 到 `limit=8`（外加各 KB 的 index 目录页作"地图"，不计入 limit），集合极小，内存过滤简单且不破坏服务层既有的"种子 > 链接 > 共享源"排序与权限不变量。把 `page_type` 下推到底层 `search_pages` 反而会割裂图扩展逻辑（链接/共享源扩展出的页也需受同一分面约束），故选择在最外层一次性过滤——"无聊但显而易见"。

**(2) Cmd-K 是纯前端组件，复用既有 `/search` 端点，不新增后端。**
`CommandPalette` 完全在 `web/src` 内实现：window 级 `keydown` 监听 `metaKey||ctrlKey + k` 切换显隐、`Escape` 关闭；输入 200ms 防抖后调 `apiFetch('/search?q=...')` 取前 8 条页结果，叠加一组静态导航项（概览/搜索/智能问答/通知/账号设置）做客户端 `includes` 匹配。点击页结果 `navigate('/pages/:id')`，点击导航项跳对应路由。
取舍理由：命令面板本质是"既有搜索 + 路由跳转"的快捷外壳，没有任何后端语义，零新增 API/表是最省的实现。

**(3) 内容健康判定全部用可移植 SQL，复用既有列，零新增表/迁移。**
三张清单的判定口径（见下）都建立在 `wiki_pages` 已有列（`updated_at`、`page_type`、`verified_at`）和 `page_links`（出/入链）之上；满意度复用阶段 5 的 `answer_feedback` 表。因此**阶段 7 没有任何新增数据库表或字段，也没有新增 alembic 迁移**。
取舍理由：分析所需信号已隐含在现有数据里，强行加埋点表只会增加写路径复杂度；治理看板对实时性要求不高，查询时聚合即可。

#### 陈旧 / 孤儿 / 待复审 的判定口径（`repositories/wiki_repo.py`）

- **陈旧页 `stale_pages(before, limit=50)`**：`page_type != "index"` 且 `updated_at < before`，按 `updated_at` 升序（最旧在前）。`before = now - stale_days`，`stale_days` 由查询参数控制（默认 90，范围 1–3650）。
- **孤儿页 `orphan_pages(limit=50)`**：`page_type != "index"` 且 `id NOT IN (SELECT from_page_id FROM page_links)` 且 `id NOT IN (SELECT to_page_id FROM page_links WHERE to_page_id IS NOT NULL)`——即**既无出链也无入链**的内容页（知识孤岛，难被发现）。注意入链子查询要求 `to_page_id IS NOT NULL`，因为 wikilink 在目标页尚未存在时 `to_page_id` 为空，不应据此把一个页算作"被链接"。
- **待复审页 `review_due_pages(before, limit=50)`**：`verified_at IS NOT NULL` 且 `verified_at < before`，按 `verified_at` 升序——即**曾被专家认证、但认证时间已超过 `stale_days` 阈值**的页，提示需要重新认证。此项跨阶段 4（认证）/阶段 7（治理展示），由 `724a4a0` 接入分析页。

#### 满意度聚合口径（`repositories/feedback_repo.py`）

`counts(session)` 执行 `SELECT vote, count(*) FROM answer_feedback GROUP BY vote`，返回 `{vote: count}` 字典。controller 取 `up`/`down` 两键（缺省 0）。前端 `AnalyticsPage` 在客户端换算满意率 `round(up / (up + down) * 100)%`，分母为 0 时显示 `—`。`answer_feedback` 的写入由阶段 5 的 `POST /api/query/feedback`（`controllers/query.py` → `feedback_repo.create`）负责，阶段 7 只做读侧聚合与展示。

---

## 4. 数据模型变更

**阶段 7 无新增表、无新增字段、无新增 alembic 迁移。** 三块能力全部复用既有 schema：

| 复用的表/列 | 用途 | 来源迁移 |
|---|---|---|
| `wiki_pages.page_type` (String(32)) | 搜索分面过滤、陈旧/孤儿判定排除 index | baseline / `56b57887b971` |
| `wiki_pages.updated_at` (DateTime tz, onupdate now) | 陈旧页判定 | baseline |
| `wiki_pages.verified_at` (DateTime tz, nullable) | 待复审判定 | `1aaf7f57b240_add_page_certification` |
| `page_links.from_page_id / to_page_id` | 孤儿页判定（出/入链） | `56b57887b971_sources_wiki_pages_page_links` |
| `answer_feedback.vote` (String(8), indexed; "up"/"down") | 满意度聚合 | `aa979a660c35_add_answer_feedback_table` |

> `page_type` 合法取值集中在模型常量 `PAGE_TYPES = ("index", "source_summary", "entity", "concept", "overview")`（`models/wiki_page.py`）。`answer_feedback.vote` 上有索引 `ix_answer_feedback_vote`，使按 vote 分组聚合走索引。

---

## 5. API 端点

| 方法 | 路径 | 鉴权 | 权限 | 说明 |
|---|---|---|---|---|
| GET | `/api/search` | 登录（`get_current_user`） | 仅返回调用者可见 KB 的页 | 入参 `q`（必填，1–500 字符）、`kb`（可选，UUID 列表，作用域收窄）、`page_type`（可选，按页类型分面）；返回 `list[SearchHit]` |
| GET | `/api/analytics` | 登录 + **admin**（`require_admin`，非 admin 403） | 管理员可见全局 | 入参 `stale_days`（默认 90，1–3650）；返回 `{feedback:{up,down}, stale_days, stale_pages[], orphan_pages[], review_due_pages[]}` |

> 路由前缀 `/api` 在 `main.py` 装配：`app.include_router(search.router, prefix="/api")`、`app.include_router(analytics.router, prefix="/api")`。
> 阶段 7 **未新增**问答反馈写入端点——`POST /api/query/feedback`（写 `answer_feedback`）属阶段 5，本阶段仅在 `/analytics` 读侧消费其聚合。

### `SearchHit` 响应结构（`schemas/wiki.py`）

`SearchHit` 继承 `PageOut`（`id` / `kb_id` / `title` / `slug` / `page_type` / `tags`），额外字段：

- `snippet: str`——围绕首个命中词截取的摘要（`make_snippet`，宽 160；无命中取开头）。
- `matched: str`——实际命中的检索词，供前端 `<mark>` 高亮。

### `/analytics` 页面摘要结构

每个清单元素为 `_page_brief(p)`：`{id, kb_id, title, updated_at}`（均序列化为字符串/ISO 时间）。

---

## 6. 权限与安全不变量

- **搜索结果隔离（铁律）**：`/api/search` 的结果集每一页的 `kb_id` 必属 `permission_service.accessible_kb_ids(user)`。`retrieval_service.retrieve` 在召回、page_links 图扩展、共享源图扩展、附 index 目录页**四个环节都做权限再过滤**（`if p.kb_id in kb_ids`）。回归测试 `test_search_filters_inaccessible` 断言平级部门（前端组）的页对后端组用户不可见。可选 `kb` 参数只能在可见域内"收窄"（`kb_ids = kb_ids & set(kb_scope)`），无法越权放大。
- **分面不绕过隔离**：`page_type` 分面在权限过滤之后施加，仅做"减法"，不引入任何跨域读取。
- **分析仅 admin**：`analytics.router` 在路由级声明 `dependencies=[Depends(require_admin)]`，非 admin 一律 403（`test_analytics_admin_only` 守护）。健康/满意度数据是全局治理视角，仅管理员可见。
- **成本上界**：`/api/search` 的 `q` 受 `max_length=500` 约束（`/api/query` 同理 `max_length=2000`，阶段 1/6 加固），在边界以 422 拒绝超长输入，防止放大下游 LLM/检索成本。
- **脱敏 N/A**：本阶段读侧聚合不涉及敏感字段透传；满意度仅暴露 up/down 计数，不回放具体问答内容到 `/analytics`。

---

## 7. 配置项

**阶段 7 无新增环境变量 / 配置项。** 三块能力均无可调参数走配置：

- 分面、命令面板：无配置。
- 内容健康阈值 `stale_days`：经 **API 查询参数**传入（默认 90，范围 1–3650），非环境变量——便于按请求调整观察窗口而无需重启。
- 满意度：直接聚合既有表，无配置。

---

## 8. 测试覆盖

### `api/tests/test_api_search_query.py`（分面相关）

- `test_search_filters_by_page_type`：对 entity 类型页，`page_type=entity` 命中 ≥1 条；`page_type=overview` 返回 `[]`（类型不匹配则空）。
- `test_search_filters_inaccessible`：搜索结果不含平级不可见部门的 KB（隔离铁律），分面建立在该隔离之上。
- （同文件还覆盖问答反馈写入 `test_query_feedback_recorded`，为满意度聚合提供数据来源；属阶段 5 但与本阶段读侧相关。）

### `api/tests/test_api_analytics.py`（内容健康 + 满意度）

- `test_analytics_orphan_stale_and_feedback`：构造一个孤儿页 + 两个互链页 + 一条 up 反馈，断言 `feedback.up == 1`，且孤儿页出现在 `orphan_pages` 而互链页 A 不在（互链页不是孤儿）。
- `test_analytics_review_due_lists_stale_verified`：构造一个 2020 年认证的页，`stale_days=30` 下断言其 id 出现在 `review_due_pages`（认证超期 → 待复审）。
- `test_analytics_admin_only`：普通用户访问 `/api/analytics` 返回 403。

> 前端无独立单测，三块 UI（`SearchPage` 分面 chips、`CommandPalette`、`AnalyticsPage`）通过 `web` 构建（`build/test`）作为关卡保障；对应 commit 记录均注明"前端构建通过"。

---

## 9. 已知限制与未来工作

对照 IMPLEMENTATION_PLAN 阶段 7 的 ⬜ 项，以下为明确未做、留待后续：

- **分面维度单一**：仅页类型一维、且单选。未做作用域 / 时间 / 知识库分面与多选组合。
- **无中文纠错**：检索为可移植 LIKE 子串匹配 + 中文相邻二元组兜底（无分词器），无拼写/纠错与同义扩展。
- **无使用行为分析**：缺活跃用户、热门页、趋势曲线；缺**搜索无果词记录**（无搜索查询日志表，无法识别"知识空缺"）。
- **健康指标为时点查询**：每次请求实时聚合，无历史快照/趋势；清单 `limit=50` 截断，大库下非全量。
- **无个性化 / 推荐 / i18n / a11y / 移动端**：发现与体验的"个性化与可达性"整块尚未启动。
- **分面在内存过滤**：当前结果集很小（limit=8）无性能问题；若未来检索改为分页/大结果集，需把 `page_type` 下推到 SQL（`wiki_repo.search_pages` 增加类型条件）以避免内存膨胀。

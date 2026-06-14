# 阶段 3：内容创作与版本 — as-built 设计文档

> 状态：as-built（已上线）· 日期：2026-06-14 · 方法论：superpowers（回溯补档）
> 对应 IMPLEMENTATION_PLAN 阶段 3 · 关联提交：
> - `741989c` feat(authoring): 人工页 CRUD + 版本历史/回滚（后端）
> - `3c27623` feat(authoring-ui): Markdown 编辑器（创建/编辑/删除）+ 历史版本查看与回滚
> - `f1bf469` docs(plan): 标记阶段 3 已完成项
> - `7263542` fix(authoring): 删除带评论的页面 500 修复 — delete_page 连带清理评论
> - `c8b8a18` feat(authoring): 版本历史行级 diff（对比上一版，增/删高亮）
> - `bc75bd1` docs(plan): 阶段 3 版本行级 diff 完成
> - `a20b9c0` feat(authoring): 页面导出 Markdown(.md 下载) — 读权限, RFC5987 文件名
>
> 说明：本组功能先开发后补档，本 spec 记录"实际建成"的设计与取舍（非事前计划）。

---

## 1. 背景与目标

在 MVP（见 `2026-06-13-enterprise-llm-wiki-mvp-design.md`）里，wiki 页面**只能由 LLM 摄入管线自动生成**——上传源文件、worker 跑两步 LLM、产出带溯源与 `[[wikilink]]` 的页面。这意味着人无法直接写一篇文档、无法修订、无法删除一条过时内容，更没有"谁改了什么、能不能退回"的历史。

对标 Confluence / Notion / Guru 这类企业知识平台，**人工内容创作与版本管理是最大产品缺口**：企业采购方的第一个"必查项"就是"我的团队能不能自己写、改、回滚 wiki"。

阶段 3 的目标即填补这块缺口：让有写权限的人**直接创建 / 编辑 / 删除**页面，并提供**版本历史 + 回滚 + 行级 diff**，同时支持把页面**导出为 Markdown 文件**便于离线留存与迁移。所有写操作复用 MVP 已有的四级权限隔离（`company` / `department` / `team` / `personal`）与审计基线，不另起炉灶。

## 2. 范围

### 2.1 ✅ 已建成

1. **人工页 CRUD**（`controllers/wiki.py`）
   - `POST /api/kbs/{kb_id}/pages` 创建：受 `can_write` 约束；`slug` 在 KB 内唯一（重复 409）；只允许人工页类型（`overview` / `entity` / `concept`），系统页类型（`index` / `source_summary`）以 422 拒绝；`slug` 留空时按标题 `slugify` 自动生成（支持 CJK）；创建即写入初始版本 v1。
   - `PUT /api/pages/{page_id}` 编辑：部分字段更新（title / content_md / page_type / tags），每次保存留一个新版本。
   - `DELETE /api/pages/{page_id}` 删除：硬删除；`index` 目录页禁止删除（400）；连带清理出/入链、历史版本、评论、收藏、订阅、通知（避免外键残留与 500）。
2. **wikilink 重建与目录刷新**：每次创建/编辑/回滚后统一执行 `_post_write_rebuild`——重抽正文里的 `[[wikilink]]` 刷新 `page_links` 图、重建 KB 的 `index` 目录页、回填链接目标 `to_page_id`。
3. **版本历史 + 回滚**（`page_versions` 表）
   - `GET /api/pages/{page_id}/versions` 列版本（`version_no` 倒序，最新在前），需读权限。
   - `POST /api/pages/{page_id}/revert/{version_no}` 回滚到指定版本：把目标版本的 title/content_md/page_type 覆盖回当前页，并把回滚结果**再存为一个新版本**（回滚也留痕，可逆）。
4. **前端 Markdown 编辑器**（`web/src/pages/PageEditPage.tsx`）：创建/编辑/删除一体，左写右览**实时预览**（复用 `components/Markdown.tsx` 渲染、`lib/wikilink.ts` 解析站内链接）。
5. **版本历史页 + 行级 diff 高亮**（`web/src/pages/PageHistoryPage.tsx` + `web/src/lib/linediff.ts`）：左侧版本列表，右侧可"看全文 / 对比上一版"切换，diff 按 LCS 算法做行级标注（新增绿底、删除红底删除线）。
6. **页面导出 Markdown**：`GET /api/pages/{page_id}/markdown` 返回 `.md` 下载，正文以 `# 标题` 开头，需读权限；文件名用 RFC 5987 `filename*` 提供 UTF-8 原名 + ASCII 兜底。

### 2.2 ⬜ 明确未做（对照 IMPLEMENTATION_PLAN 阶段 3）

- **草稿 → 评审 → 发布 状态机**：当前没有页面发布状态，保存即对所有可读者可见（也会进检索/RAG）。未实现，避免半成品污染检索的诉求暂未覆盖。
- **软删除 / 回收站 / 恢复**：当前 `DELETE` 是**硬删除**（连带级联清理），无回收站、无恢复入口。

## 3. 架构与关键设计决策

### 3.1 分层落点

沿用 MVP 的 Controller–Service–Repository 分层，本阶段写操作落点如下：

```
controllers/wiki.py        HTTP 端点：鉴权(get_current_user) + 权限(can_write/accessible) +
                           参数校验(slug/page_type) + 审计/通知/webhook 编排 + 事务提交
   │
   ├─ services/permission_service.py   can_write / accessible_kb_ids（隔离不变量）
   ├─ services/kb_service.py           rebuild_index（重建 KB 目录页）
   ├─ services/audit_service.py        record（page.create/update/delete/revert 审计）
   ├─ services/notification_service.py notify_watchers（编辑通知订阅者）
   ├─ services/webhook_service.py      dispatch（page.updated 出站事件）
   │
   └─ repositories/wiki_repo.py        upsert / delete_page / add_version /
                                       list_versions / get_version / replace_links /
                                       backfill_link_targets
          │
          └─ models/page_version.py (PageVersion) · models/wiki_page.py (WikiPage)
```

### 3.2 关键设计决策与取舍

- **版本快照为整页全文，而非 diff 存储**。`page_versions` 每条记录存某一版的 title/page_type/content_md 全文。取舍：实现"无聊且显而易见"——回滚就是把某行整页覆盖回来；diff 在**前端按需计算**（`linediff.ts`），不占数据库。代价是大页面多次修订有存储冗余，但企业 wiki 单页体量有限（`content_md` 上限 200_000 字符），换来的简单性更划算。
- **版本号按页单调递增，在写入时取 `max(version_no)+1`**（`wiki_repo.add_version`），由 `(page_id, version_no)` 唯一约束 `uq_pageversion_page_no` 兜底。第一版 v1 在创建时即写入，保证历史从第一笔就完整。
- **回滚不是"删除后续版本"，而是"前进出一个新版本"**。`revert` 把旧内容覆盖回当前页后再 `add_version`，因此 `v1→v2→回滚v1` 得到的历史是 `[v3, v2, v1]`（v3 内容等于 v1）。这样回滚本身可被再次回滚，操作链完全可逆、可审计（审计记 `to_version`）。
- **统一写后处理 `_post_write_rebuild`**：create/update/revert 三条写路径共用同一段"刷链接图 + 重建 index + 回填链接目标"，避免三处各写一遍导致漂移。
- **删除采用硬删除 + 显式级联清理**，而非数据库 `ON DELETE CASCADE`。`wiki_repo.delete_page` 在应用层逐表删除 page_links（出/入链）、page_versions、comments、favorites、subscriptions、notifications，再删页本身。取舍：保持各表外键约束简单、级联范围在代码里一目了然；`7263542` 即为补齐评论清理修复删除带评论页面的 500。
- **导出在 controller 内直接组装**，不引专门的导出服务：正文 = `# {title}` + 空行 + `content_md`，无额外渲染。简单到不值得抽象。

### 3.3 数据流：编辑一次的完整链路

```
PUT /api/pages/{id}  body={title?,content_md?,page_type?,tags?}
  → _writable_page: 取页 → 取 KB → can_write 校验（否则 404/403）
  → page_type 若给定且非 HUMAN_PAGE_TYPES → 422
  → 按字段更新 page（仅更新非 None 字段）
  → session.flush()
  → wiki_repo.add_version(page, edited_by=user.id)   # 留版本
  → _post_write_rebuild: replace_links → rebuild_index → backfill_link_targets
  → audit_service.record(action="page.update")
  → notification_service.notify_watchers(type="page.updated")
  → webhook_service.dispatch("page.updated", {...})
  → session.commit()
  → 返回 PageDetailOut（含 backlinks/outlinks/sources 等，均按可见域过滤）
```

## 4. 数据模型变更

### 4.1 新增表：`page_versions`

迁移文件：`api/migrations/versions/e92b82749b50_add_page_versions_table.py`（down_revision = `1245f96cd622`）。
模型：`api/app/models/page_version.py` 的 `PageVersion`。

| 列名 | 类型 | 约束 / 说明 |
|---|---|---|
| `id` | `Uuid` | 主键，默认 `uuid4` |
| `page_id` | `Uuid` | 外键 → `wiki_pages.id`，建索引 `ix_page_versions_page_id` |
| `version_no` | `Integer` | 非空，按页 1 起单调递增 |
| `title` | `String(512)` | 非空，快照标题 |
| `page_type` | `String(32)` | 非空，快照页类型 |
| `content_md` | `Text` | 非空（默认 `""`），快照正文 |
| `edited_by` | `Uuid` | 可空，外键 → `users.id`（回滚/编辑者） |
| `created_at` | `DateTime(timezone=True)` | `server_default=now()` |

唯一约束：`uq_pageversion_page_no = UniqueConstraint(page_id, version_no)`——同一页版本号不重复。

### 4.2 既有表沿用（非本阶段新增）

- `wiki_pages`（`models/wiki_page.py`）：CRUD 直接读写该表，未在本阶段加字段。其中 `tags`（JSON）字段属阶段 4 协作能力（迁移 `b17ca4b2da9b_add_wiki_pages_tags`），CRUD 端点顺带支持读写，但**不是阶段 3 的数据模型变更**。`verified_by` / `verified_at` 同属阶段 4 内容认证（迁移 `1aaf7f57b240`）。
- `page_links`（`models/page_link.py`）：wikilink 图，写后由 `replace_links` / `backfill_link_targets` 维护，非本阶段新增。

## 5. API 端点

所有端点挂在 `wiki.router`，统一前缀 `/api`（`main.py` 装配）。鉴权统一走 `get_current_user`（JWT）。

| 方法 | 路径 | 鉴权 | 权限要求 |
|---|---|---|---|
| `POST` | `/api/kbs/{kb_id}/pages` | 登录 | 对该 KB `can_write`；`page_type ∈ {overview, entity, concept}`；`slug` 唯一 |
| `PUT` | `/api/pages/{page_id}` | 登录 | 对页所在 KB `can_write` |
| `DELETE` | `/api/pages/{page_id}` | 登录 | 对页所在 KB `can_write`；`index` 页禁删 |
| `GET` | `/api/pages/{page_id}/versions` | 登录 | 页所在 KB 在 `accessible_kb_ids`（读权限） |
| `POST` | `/api/pages/{page_id}/revert/{version_no}` | 登录 | 对页所在 KB `can_write` |
| `GET` | `/api/pages/{page_id}/markdown` | 登录 | 页所在 KB 在 `accessible_kb_ids`（读权限） |

请求/响应模型（`schemas/wiki.py`）：

- `PageCreate`：`title`(1..512) / `slug?`(<=512) / `content_md`(<=200_000) / `page_type`(默认 `concept`) / `tags`(<=30 项)
- `PageUpdate`：同上字段全部可空，部分更新
- `PageVersionOut`：`version_no` / `title` / `page_type` / `content_md` / `edited_by?` / `created_at`
- `PageDetailOut`（create/update/revert 返回）：含 `content_md` / `frontmatter` / `source_ids` / `backlinks` / `outlinks` / `sources` / `tags` / 认证字段等，均按可见域过滤后返回

状态码约定：创建 201、删除 204、slug 冲突 409、系统页类型/非法 slug 422、无写权限 403、页/版本不存在 404、删 index 页 400。

导出响应：`media_type = "text/markdown; charset=utf-8"`，`Content-Disposition: attachment; filename="{ascii}.md"; filename*=UTF-8''{slug}.md`（RFC 5987）。

## 6. 权限与安全不变量

- **写操作一律过 `can_write`**：`_writable_page` 取页后取 KB 再判 `can_write`，失败返回 403（页本身不存在返回 404）。`can_write` 的语义：personal 仅本人、team 看 `UserTeam.can_write`（只读成员为 False）、department/company 仅 admin。
- **读操作（versions / markdown / detail）过 `accessible_kb_ids`**：页所在 KB 不在可见集合即 403，杜绝跨作用域窥探历史与导出他人 KB 内容。
- **系统页类型不可由人工创建/改写**：`HUMAN_PAGE_TYPES = ("overview","entity","concept")`，`index`（目录）与 `source_summary`（源摘要）由系统维护，create/update 指定它们以 422 拒绝；`index` 页禁止删除（400），保证目录页始终存在。
- **slug 唯一性**：创建时 `get_by_slug` 命中即 409，配合 `wiki_pages` 的 `uq_wiki_kb_slug` 约束，防止同 KB 重名页。
- **详情返回按可见域过滤关联**：`_build_detail` 对 backlinks / outlinks / sources 逐一过滤 `kb_id ∈ accessible`——晋升等路径可能让页的 `source_ids` 指向跨作用域 Source，过滤后不泄漏他人作用域的源文件名。
- **全程审计留痕**：create/update/delete/revert 均 `audit_service.record`，detail 里带 `kb_id` / `slug` / `to_version` 等上下文，满足企业合规留证。
- **导出文件名安全**：slug 经 `quote` 编码进 `filename*`，ASCII 兜底用 `encode("ascii","ignore")`，避免头注入与非 ASCII 文件名乱码。

## 7. 配置项

本阶段**未新增任何环境变量 / 配置项**（N/A）。CRUD、版本历史、回滚、行级 diff、导出均无可调开关；字段长度上限（`title<=512`、`content_md<=200_000`、`tags<=30`）写死在 `schemas/wiki.py` 的 `Field` 约束里，非运行期配置。

## 8. 测试覆盖

### 8.1 后端（`api/tests/test_api_wiki.py`，端到端）

| 测试函数 | 覆盖点 |
|---|---|
| `test_create_edit_history_revert_flow` | 创建→编辑→列版本（`[2,1]`）→回滚 v1→版本变 `[3,2,1]` 且内容回到第一版 |
| `test_export_page_markdown` | 导出返回 200、`text/markdown`、正文含 `# 标题` 与正文 |
| `test_create_page_forbidden_without_write` | 无写权限创建 403 |
| `test_create_page_duplicate_slug_conflict` | 重复 slug 409 |
| `test_create_rejects_system_page_type` | `page_type=index` 创建 422 |
| `test_delete_page` | 删除成功（204/不存在） |
| `test_delete_page_with_comment_succeeds` | 删除带评论页面不再 500（级联清理） |
| `test_page_tags_create_and_filter` | 创建带标签 + 按 tag 过滤列表（标签属阶段 4，CRUD 顺带覆盖） |
| `test_get_page_hides_cross_kb_source_filenames` | 详情按可见域过滤源文件名 |
| `test_get_page_includes_outlinks` | wikilink 出链解析 |

> `api/tests/test_wiki_repo.py` 覆盖仓储层 upsert 幂等、replace_links/backfill、outlinks 解析；版本历史/回滚的回归在上面的端到端用例中验证，仓储层未另写版本专项单测。

### 8.2 前端（`web/src/lib/linediff.test.ts`，vitest）

| 用例 | 覆盖点 |
|---|---|
| 「标注新增、删除与未变行」 | LCS 行级 diff 正确产出 same/add/del |
| 「内容相同则全部为 same」 | 无差异时不误报增删 |

## 9. 已知限制与未来工作

对照 roadmap 阶段 3 的 ⬜ 项与实现现状：

- **⬜ 草稿 → 评审 → 发布 状态机**：当前保存即发布、即进检索/RAG，缺少"半成品隔离"。未来需为页面引入发布状态字段与评审流转。
- **⬜ 软删除 / 回收站 / 恢复**：当前为硬删除（含级联清理），误删不可恢复。未来需改为软删除标记 + 回收站列表 + 恢复入口。
- **diff 仅"对比上一版"**：前端历史页只支持选中版本与其紧邻上一版做行级 diff，尚不支持任意两版对比。
- **版本无保留上限 / 无清理策略**：每次保存与回滚都累积一条全文快照，长期高频编辑的页面会持续增长，暂无版本数上限或归档策略。
- **导出仅单页 Markdown**：无整 KB 批量导出、无 PDF / HTML 等其它格式（其它格式导出见阶段 8 路线图的源类型扩展，非本阶段）。

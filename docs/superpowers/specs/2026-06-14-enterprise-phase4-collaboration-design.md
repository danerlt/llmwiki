# 阶段 4：协作（把 IM 讨论沉淀回知识）— as-built 设计文档

> 状态：as-built（已上线）· 日期：2026-06-14 · 方法论：superpowers（回溯补档）
> 对应 IMPLEMENTATION_PLAN 阶段 4 · 关联提交：
> - `9da335a` feat(collab): 页面订阅(关注)+ 站内通知 + 收件箱(后端)
> - `320f4b8` feat(collab-ui): 订阅/通知前端 — 详情关注按钮 + 通知收件箱 + 侧栏未读角标
> - `b12f072` feat(collab): 内容认证(专家背书) — 认证/取消, 详情徽章
> - `304fc66` feat(collab): 活动流 — 可见库内页面更新+评论合并时间线(仪表盘)
> - `724a4a0` feat(governance): 过期复审提醒 — 认证超期内容进入分析「待复审」
> - 评论/标签/收藏：随 `5282456`「阶段4协作进度(评论/标签/收藏/订阅通知)」一并落地
>
> 说明：本组功能先开发后补档，本 spec 记录"实际建成"的设计与取舍（非事前计划）。

---

## 1. 背景与目标

LLM-Wiki 把源文档编译为结构化知识页，但**沉淀**只是第一步——企业采购对标 Confluence/Notion/Guru 时，会查"知识能不能被讨论、被组织、被信任、被追踪"。阶段 1–3 解决了"内容怎么进来、怎么编辑、怎么留版本"，阶段 4 补齐的是**协作与留存命脉**：

- **就地讨论**：把散落在 IM 群里的口头结论沉淀回页面（页面评论）。
- **组织与发现**：标签分类、个人收藏，让知识可被归类、可被快速回到。
- **可信度信号**：内容认证（专家背书）+ 徽章，区分"权威内容"与"草稿"。
- **不漏过更新**：页面订阅（watch）+ 站内通知收件箱，关注的页一有动静就收到提醒。
- **治理闭环**：认证内容会过期，超期自动进入分析仪表盘的「待复审」，避免权威信息腐化。
- **全局动态**：可见库内的页面更新与评论合并成时间线，落在仪表盘。

设计取舍上全程坚持"无聊、显而易见"：评论是**扁平线程**（不做嵌套回复树），通知是**同步直发**（不引入事件总线），认证是**单一背书者**（不做多人会签）。这些都在第 9 节如实标注为已知边界。

---

## 2. 范围

### ✅ 已建成

| 能力 | 落点 | 状态 |
|---|---|---|
| 页面评论 / 讨论线程（读权限可评、作者或 admin 可删、审计） | `controllers/comments.py` | ✅ |
| 标签（创建/编辑时写入、详情展示、按标签过滤列表） | `controllers/wiki.py` | ✅ |
| 收藏（星标 + 我的收藏，作用域感知） | `controllers/favorites.py` | ✅ |
| 内容认证（专家背书：认证/取消 + 详情徽章） | `controllers/wiki.py` | ✅ |
| 页面订阅（watch）+ 站内通知收件箱（标记已读 + 未读计数） | `controllers/notifications.py` | ✅ |
| 编辑/评论自动通知关注者（排除操作者本人） | `services/notification_service.py` | ✅ |
| 侧栏未读角标（轮询 unread-count） | `web/src/components/Layout.tsx` | ✅ |
| 活动流（可见库内 页面更新 + 评论 合并时间线） | `controllers/activity.py` | ✅ |
| 过期复审提醒（认证超期内容进入分析「待复审」） | `controllers/analytics.py` | ✅ |

### ⬜ 明确未做（对照 IMPLEMENTATION_PLAN 阶段 4）

- ⬜ @提及（人员/页面自动补全）
- ⬜ 邮件通知渠道（仅站内通知）
- ⬜ KB 级订阅（仅页级 watch）
- ⬜ 领域事件总线（当前为同步直发，规模化时再抽象）

> **与 roadmap 勾选状态的核对**：IMPLEMENTATION_PLAN 第 61 行将"活动流""过期复审提醒"勾为 ✅。经核实，`controllers/activity.py`（`/activity` 端点）与 `controllers/analytics.py` 的 `review_due_pages` 均**真实建成且有测试覆盖**，勾选状态与代码**一致**，不存在"勾了但没做"的虚标。详见第 5、8 节。

---

## 3. 架构与关键设计决策

### 3.1 分层落点

沿用项目既定的 Controller–Service–Repository 分层。阶段 4 各能力的落点：

```
评论       comments.py(controller) ─► comment_repo / user_repo / wiki_repo
                                  └─► audit_service / notification_service / webhook_service
收藏       favorites.py(controller) ─► favorite_repo / wiki_repo + permission_service
订阅/通知  notifications.py(controller) ─► subscription_repo / notification_repo / wiki_repo
           编辑/评论触发 ─► notification_service ─► subscription_repo + notification_repo
标签       wiki.py(controller) ─► WikiPage.tags(JSON 列) 直接读写
认证       wiki.py(controller) ─► WikiPage.verified_by/verified_at 直接读写 + audit_service
活动流     activity.py(controller) ─► wiki_repo.recent + comment_repo.recent_in_kbs
过期复审   analytics.py(controller) ─► wiki_repo.review_due_pages
```

### 3.2 关键设计决策与理由

1. **评论无独立 service 层**：评论业务逻辑（建/删/列、权限校验、审计、通知、webhook 编排）全部落在 `comments.py` 控制器里，仅持久化下沉到 `comment_repo`。原因：评论是薄 CRUD，没有跨控制器复用的业务规则，过早抽出 `comment_service` 属于"过早抽象"。**唯一被复用的协作逻辑**——"通知关注者"——才下沉成 `notification_service`，因为评论与页面编辑两处都要用它。

2. **扁平线程，非嵌套树**：`comments` 表无 `parent_id`，按 `created_at` 升序平铺。讨论沉淀的核心价值是"留下结论"，嵌套回复树会显著增加前后端复杂度，按 YAGNI 暂不做。

3. **标签/认证字段内嵌 `wiki_pages`，不另建表**：
   - 标签存为 `wiki_pages.tags`（JSON 数组），过滤在应用层做 `tag in page.tags`。原因：标签是页的从属属性、基数小、无独立生命周期；建 `tags` + `page_tags` 关联表是过度设计。代价是无法对标签做高效 SQL 聚合（如全局标签云），但当前 KB 体量下可接受。
   - 认证存为 `wiki_pages.verified_by`（外键 users）+ `verified_at`（时间戳）。认证是页的**单一状态**而非事件流，内嵌字段最简单；`verified_at` 同时承担"过期复审"的判定依据，一字段两用。

4. **通知同步直发，随业务事务提交**：`notification_service.notify_watchers` 在编辑/评论的同一个 DB 事务里给每个关注者 `INSERT` 一行通知，**不 commit**（由调用方业务 commit）。保证"业务成功 ⇔ 通知已落库"的原子性，避免半状态。代价是关注者多时为 N 次插入的同步循环——规模化时才需要事件总线/异步扇出（已在 roadmap 标 ⬜）。

5. **操作者本人不通知自己**：`notify_watchers` 内 `if uid == actor_id: continue`，避免"自己编辑自己被提醒"的噪音。

6. **作用域感知贯穿读路径**：收藏列表、活动流只返回**当前仍可见**的页（`page.kb_id in accessible`）。因为用户的可见作用域可能在收藏后发生变化（团队调动、KB 权限回收），过滤在读时做，避免泄漏已失去权限的页。

7. **认证与过期复审解耦**：认证端点只负责打/撤标记；"是否过期"由 `analytics.py` 在读时用 `verified_at < (now - stale_days)` 现算，**不存"是否过期"的冗余状态**，也不跑定时任务。显式优于隐式，且无后台调度依赖。

---

## 4. 数据模型变更

### 4.1 新增表

#### `comments`（迁移 `df8ad50a0b35_add_comments_table`）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Uuid | PK |
| `page_id` | Uuid | FK→`wiki_pages.id`, index `ix_comments_page_id` |
| `author_id` | Uuid | FK→`users.id` |
| `body` | Text | NOT NULL |
| `created_at` | DateTime(tz) | server_default `now()`, NOT NULL |

#### `favorites`（迁移 `4b50a583db74_add_favorites_table`）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Uuid | PK |
| `user_id` | Uuid | FK→`users.id`, index `ix_favorites_user_id` |
| `page_id` | Uuid | FK→`wiki_pages.id`, index `ix_favorites_page_id` |
| `created_at` | DateTime(tz) | server_default `now()`, NOT NULL |

唯一约束 `uq_favorite_user_page (user_id, page_id)`——同一用户不可重复收藏同一页。

#### `subscriptions`（迁移 `ff5e58059194_add_subscriptions_and_notifications`）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Uuid | PK |
| `user_id` | Uuid | FK→`users.id`, index `ix_subscriptions_user_id` |
| `page_id` | Uuid | FK→`wiki_pages.id`, index `ix_subscriptions_page_id` |
| `created_at` | DateTime(tz) | server_default `now()`, NOT NULL |

唯一约束 `uq_subscription_user_page (user_id, page_id)`——同一用户对同一页只关注一次。

#### `notifications`（迁移 `ff5e58059194_add_subscriptions_and_notifications`）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Uuid | PK |
| `user_id` | Uuid | FK→`users.id`, index `ix_notifications_user_id`（收件人） |
| `type` | String(32) | NOT NULL（`page.updated` / `page.commented`） |
| `page_id` | Uuid | FK→`wiki_pages.id`, nullable |
| `actor_id` | Uuid | FK→`users.id`, nullable（触发者） |
| `message` | Text | NOT NULL（预渲染中文文案） |
| `read` | Boolean | server_default `false`, NOT NULL |
| `created_at` | DateTime(tz) | server_default `now()`, NOT NULL |

### 4.2 既有表新增列

#### `wiki_pages` 新增 `tags`（迁移 `b17ca4b2da9b_add_wiki_pages_tags`）

| 列 | 类型 | 约束 |
|---|---|---|
| `tags` | JSON | NOT NULL, server_default `'[]'`（回填存量行避免 NULL） |

#### `wiki_pages` 新增认证字段（迁移 `1aaf7f57b240_add_page_certification`）

| 列 | 类型 | 约束 |
|---|---|---|
| `verified_by` | Uuid | FK→`users.id`（约束名 `fk_wiki_pages_verified_by`）, nullable |
| `verified_at` | DateTime(tz) | nullable |

---

## 5. API 端点

所有路由统一挂在 `/api` 前缀下（`main.py` 中 `include_router(..., prefix="/api")`）。除特别说明外，均要求登录用户（`Depends(get_current_user)`）。

### 5.1 评论（`comments.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| GET | `/api/pages/{page_id}/comments` | 对该页有读权限（`accessible_kb_ids`） | 按 `created_at` 升序返回，含 `author_name` |
| POST | `/api/pages/{page_id}/comments` | 对该页有**读**权限即可评论 | 201；写审计 `comment.create`；通知关注者；派发 webhook `page.commented` |
| DELETE | `/api/comments/{comment_id}` | **作者本人或 admin** | 204；写审计 `comment.delete` |

### 5.2 收藏（`favorites.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| GET | `/api/favorites` | 登录用户 | 仅返回当前仍可见（`kb_id in accessible`）的收藏页 |
| POST | `/api/pages/{page_id}/favorite` | 对该页有读权限 | 204；幂等（`favorite_repo.add` 存在则跳过） |
| DELETE | `/api/pages/{page_id}/favorite` | 登录用户 | 204；幂等删除 |

### 5.3 订阅与通知（`notifications.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| POST | `/api/pages/{page_id}/subscribe` | 对该页有读权限 | 204；幂等 |
| DELETE | `/api/pages/{page_id}/subscribe` | 登录用户 | 204；幂等 |
| GET | `/api/notifications` | 登录用户 | 收件箱：本人通知，按 `created_at` 倒序，最多 30 条 |
| GET | `/api/notifications/unread-count` | 登录用户 | 返回 `{"count": N}`，供侧栏角标轮询 |
| POST | `/api/notifications/read` | 登录用户 | 204；本人全部未读标记为已读 |

### 5.4 标签 / 认证（`wiki.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| GET | `/api/kbs/{kb_id}/pages?tag=<标签>` | 对该 KB 可见 | `tag` 查询参数可选，按标签应用层过滤 |
| POST | `/api/kbs/{kb_id}/pages` | `can_write` | 创建时写入 `tags`（去空白） |
| PUT | `/api/pages/{page_id}` | `can_write` | `tags` 非空时覆盖；编辑同时通知关注者 + webhook `page.updated` |
| POST | `/api/pages/{page_id}/verify` | `can_write`（`_writable_page`） | 认证为权威内容，置 `verified_by/verified_at`；写审计 `page.verify` |
| DELETE | `/api/pages/{page_id}/verify` | `can_write` | 取消认证，清空两字段；写审计 `page.unverify` |
| GET | `/api/pages/{page_id}` | 对该页有读权限 | 详情返回 `tags` / `verified_at` / `verified_by_name` / `is_favorited` / `is_subscribed` |

### 5.5 活动流（`activity.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| GET | `/api/activity` | 登录用户 | 可见库内 页面更新(`wiki_repo.recent` 15 条) + 评论(`comment_repo.recent_in_kbs` 15 条) 合并按时间倒序，截断取前 20 |

### 5.6 过期复审（`analytics.py`）

| 方法 | 路径 | 鉴权与权限 | 说明 |
|---|---|---|---|
| GET | `/api/analytics?stale_days=<N>` | **admin**（`require_admin`，路由级依赖） | 返回体含 `review_due_pages`：`verified_at < (now - stale_days)` 的认证超期页 |

---

## 6. 权限与安全不变量

- **读权限闸门统一**：评论、收藏、订阅的"取页"前置 `_readable_page` 均调用 `permission_service.accessible_kb_ids`，页所属 KB 不在可见集合即 403；页不存在即 404。三处控制器各自持有结构相同的 `_readable_page` helper（薄校验，未强行抽公共函数）。
- **写权限闸门（认证）**：`/verify`、`/unverify` 走 `_writable_page` → `permission_service.can_write`，只有对该页所在 KB 有写权限者能背书/撤销，普通读者不能伪造权威标记。
- **评论删除越权防护**：`DELETE /comments/{id}` 校验 `c.author_id == user.id or user.role == "admin"`，他人不可删别人评论（测试 `test_non_author_cannot_delete_comment` 覆盖）。
- **作用域变更后的脱敏**：收藏列表、活动流在**读时**按当前 `accessible` 过滤，用户失去某 KB 权限后，其旧收藏/动态中该库的页不再出现，避免越权泄漏标题等元数据。
- **通知不跨权限泄漏内容**：通知 `message` 为预渲染文案（如"X 编辑了《标题》"），仅发给本就关注该页（即曾有读权限）的订阅者；点开仍走 `/pages/{id}` 的读权限校验，通知本身不绕过 ACL。
- **自我通知抑制**：`notify_watchers` 排除 `actor_id`，操作者不会收到自己动作的提醒（测试 `test_actor_not_notified_of_own_edit` 覆盖）。
- **过期复审仅管理员可见**：`/analytics` 整个路由挂 `require_admin`，治理视图不对普通用户暴露。

---

## 7. 配置项

**N/A** —— 阶段 4 未引入任何新环境变量/配置项（已核实 `core/config.py` 无评论/收藏/订阅/通知/认证/复审相关配置）。

相关可调参数均为**端点查询参数**而非配置：
- 过期判定阈值：`GET /api/analytics?stale_days=N`（默认 90，范围 1–3650），由调用方按需传入，复用"内容健康/陈旧页"的同一阈值。
- 各列表上限（评论无限制、通知 30、活动流 15+15→20）为代码内常量，非配置。

---

## 8. 测试覆盖

| 测试文件 | 关键用例 | 验证点 |
|---|---|---|
| `api/tests/test_api_comments.py` | `test_add_list_delete_comment` | 评论增/列/删全链路 |
| | `test_cannot_comment_on_inaccessible_page` | 无读权限页评论被 403 |
| | `test_non_author_cannot_delete_comment` | 非作者删评论被拒 |
| `api/tests/test_api_favorites.py` | `test_favorite_toggle_and_list` | 收藏开关 + 我的收藏列表 |
| `api/tests/test_api_notifications.py` | `test_subscribe_then_edit_notifies_watcher` | 关注后被编辑→关注者收到通知 |
| | `test_actor_not_notified_of_own_edit` | 操作者本人不被自己的编辑通知 |
| `api/tests/test_api_activity.py` | `test_activity_merges_updates_and_comments` | 活动流合并页面更新与评论 |
| `api/tests/test_api_wiki.py` | `test_page_tags_create_and_filter` | 创建带标签 + `?tag=` 过滤 |
| | `test_page_verify_and_unverify` | 认证（含 `verified_by_name`）/取消认证 |
| `api/tests/test_api_analytics.py` | `test_analytics_review_due_lists_stale_verified` | 认证超期页进入 `review_due_pages` |

> 测试模式说明：均为基于 `session` + `client` fixture 的端到端控制器测试，沿用项目既有 `test_api_*` 约定，行为可确定性复现。

---

## 9. 已知限制与未来工作

对照 IMPLEMENTATION_PLAN 阶段 4 的 ⬜ 项与本期实现取舍：

- **⬜ @提及**：评论 `body` 为纯文本，无人员/页面补全与定向通知。需新增提及解析 + 被提及者通知通道。
- **⬜ 邮件渠道**：通知仅站内（`notifications` 表 + 收件箱 + 角标），无 SMTP/邮件投递。
- **⬜ KB 级订阅**：订阅粒度仅到页（`subscriptions(user_id, page_id)`），无法一键关注整库新增/变更。
- **⬜ 领域事件总线**：编辑/评论的通知与 webhook 为**同步直发**（控制器内顺序调用 `notification_service` + `webhook_service`）。关注者多或下游慢时会拖长请求；规模化时再抽象为异步事件扇出。
- **扁平评论**：无嵌套回复、无编辑（仅建/删），讨论以时间线呈现。
- **标签无全局聚合**：标签存 JSON 列、过滤在应用层，暂不支持标签云/重命名/合并等全局操作。
- **认证为单人背书**：`verified_by` 单一外键，无多人会签/审批流；取消认证不留历史快照（仅审计事件 `page.unverify` 留痕）。
- **过期复审为被动展示**：超期页仅在管理员打开 `/analytics` 时现算列出，无主动推送/邮件催办（与"⬜ 邮件渠道"同源）。

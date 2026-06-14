# 阶段 8：外部集成（API Key / 服务账号 + 出站 Webhook）— as-built 设计文档

> 状态：as-built（已上线）· 日期：2026-06-14 · 方法论：superpowers（回溯补档）
> 对应 IMPLEMENTATION_PLAN 阶段 8「外部集成与多租户」· 关联提交：
> - `7cdd394` feat(api): API Key / 服务账号 — 编程接入(X-API-Key), 创建/列出/吊销 + 设置页管理
> - `07135f4` docs(plan): 阶段8 API Key 服务账号起步
> - `8c0a39a` feat(integration): 出站 Webhook 事件订阅(HMAC签名) — 页面更新/评论推送外部
> - `3b2fd9f` docs(plan): 阶段8 Webhook 完成
>
> 说明：本组功能先开发后补档，本 spec 记录“实际建成”的设计与取舍（非事前计划）。所有端点、表、迁移文件、测试均已对照 working tree 当前代码逐项核实。

---

## 1. 背景与目标

阶段 8 的命题是把 Lumen 从“封闭的知识孤岛”变成“可被外部系统编程接入、并能向外广播事件的企业事件枢纽”。它填补两个典型的企业采购缺口：

1. **编程接入（machine-to-machine）**：CI 机器人、内部脚本、数据同步作业需要在没有人工登录、没有交互式 JWT 流程的前提下以稳定凭据调用平台 API。企业要求这种凭据可被审计、可被随时吊销、且泄露后影响面可控。
2. **出站事件订阅（outbound integration）**：当知识库内容发生变化（页面被编辑、被评论），企业希望把事件实时推送到 IM 机器人、自动化流水线或第三方系统，由对方据此触发后续动作；同时接收方需要一种方式验证“这条推送确实来自 Lumen、且未被篡改”。

本阶段实际只交付了上述两项（API Key 与出站 Webhook）。阶段标题里同时挂着的“多租户隔离层”“更多数据源”属同一阶段的未完成项，见第 9 节。

## 2. 范围

### 2.1 ✅ 已建成

- **对外 REST API + API Key / 服务账号**
  - 以 `X-API-Key` 请求头编程接入；凭据以 owner 用户身份执行（服务账号 = 借用某真人账号身份），自动继承该用户的角色与可见 KB 范围。
  - 密钥生命周期：创建（明文仅返回一次）/ 列出（按当前用户）/ 吊销（软删，`revoked=true`）。
  - 库内仅存 `sha256` 哈希，绝不落明文。
  - 前端「设置页」`SettingsPage.tsx` 提供 API Key 的创建 / 列表 / 吊销管理界面。
- **出站 Webhook 事件订阅**
  - 管理员注册外部 URL + 共享 secret；页面更新 / 页面评论时向所有启用的 webhook POST 一条 JSON 载荷。
  - 每条投递带 HMAC-SHA256 签名头 `X-Lumen-Signature`，接收方据 secret 验证来源与完整性。
  - best-effort 投递：失败仅告警日志，不阻塞、不回滚主业务事务。

### 2.2 ⬜ 明确未做（同属阶段 8，本期未交付）

- **多租户隔离层（organization / tenant 硬隔离）** — 仍为单组织模型；是否做成多客户 SaaS 硬隔离待老板拍板（属较大架构改造）。
- **更多数据源** — docx / pptx / xlsx / html / 网页抓取 / Confluence 导入 / 扫描件 OCR 均未做。
- **真实 PG 集成测试** — 消除 SQLite ↔ PG 漂移的集成测试未补（注：GitHub Actions CI/CD 流水线本身已建成，见第 9 节订正说明）。

### 2.3 本阶段范围内、但实现弱于宣传的点（如实标注）

- **Webhook 无前端管理界面**：Webhook 的创建 / 列出 / 删除仅有后端 admin REST 端点，`SettingsPage.tsx` 与前端 `api/types.ts` 中**没有** Webhook 相关 UI 或类型。前端可管理的只有 API Key。
- **Webhook 无失败重试**：投递为一次性 best-effort，失败只写 `warning` 日志，没有重试队列、没有退避、没有死信。详见第 3.4 节。
- **`last_used_at` 字段存在但未回写**：`api_keys.last_used_at` 列与 schema 字段均已建成，但鉴权解析路径 `api_key_service.resolve()` 当前不更新它，故该字段恒为 `NULL`。

## 3. 架构与关键设计决策

整体遵循项目既有的 Controller–Service–Repository 分层。两条特性各自落点如下：

```
API Key / 服务账号
  core/deps.py            get_current_user —— X-API-Key 与 JWT 双鉴权统一入口
  controllers/api_keys.py 创建/列出/吊销 端点
  services/api_key_service.py  issue() 生成+哈希；resolve() 校验+解析 owner
  repositories/api_key_repo.py  按 hash/按 user/按 id 查询
  models/api_key.py       ApiKey 表
  schemas/api_key.py      ApiKeyCreate / ApiKeyOut / ApiKeyCreated

出站 Webhook
  controllers/webhooks.py 注册/列出/删除（admin only）
  services/webhook_service.py  sign() HMAC 签名；dispatch() best-effort 投递
  repositories/webhook_repo.py  list_active / list_all / create / get_by_id
  models/webhook.py       Webhook 表
  schemas/webhook.py      WebhookCreate / WebhookOut
  触发点：controllers/wiki.py（page.updated）、controllers/comments.py（page.commented）
```

### 3.1 API Key 的哈希存储与校验

- **格式**：明文形如 `lk_<prefix>_<secret>`。`prefix = secrets.token_hex(4)`（8 个十六进制字符，仅用于 UI 标识，不参与鉴权强度）；`secret = secrets.token_urlsafe(32)`（高熵随机串）。
- **存储**：库内只存 `key_hash = sha256(明文).hexdigest()`（64 位十六进制），并对该列加 `unique` 约束 + 索引。明文只在创建响应里返回一次（`ApiKeyCreated.key`），此后任何接口都不再回显。
- **为何用裸 sha256 而非 bcrypt/argon2**：API Key 本身是 256-bit 量级的高熵随机串，不存在“弱口令被字典爆破”的威胁模型，因此无需慢哈希加盐；用快速 sha256 既能保证“常量级查表校验”，又便于对 `key_hash` 直接建唯一索引做 O(1) 命中。这与用户口令（低熵、必须 bcrypt 慢哈希）是两套不同的安全模型，刻意区别对待。
- **校验**：`resolve(raw)` 把传入明文重新 sha256 后,在 `api_key_repo.get_by_hash` 里以 `key_hash == ? AND revoked == false` 命中记录；再回查 owner 用户，要求 `user.is_active` 为真，否则视为无效。即“吊销密钥”与“停用账号”任一条件不满足都会令 Key 失效。

### 3.2 X-API-Key 与 JWT 双鉴权如何共存

二者统一收敛到 `core/deps.py::get_current_user` 这一个依赖里，按固定优先级处理：

1. **X-API-Key 优先**：若请求头带 `X-API-Key`，走 `api_key_service.resolve()`；解析失败立即 `401 invalid api key`，**不再回退尝试 JWT**（避免“无效 Key + 残留 JWT”造成的歧义鉴权）。
2. **否则走 JWT Bearer**：`HTTPBearer(auto_error=False)` 取 token，`decode_token` 解出 `sub`，回查用户，并校验 `is_active` 与会话版本 `tv == user.token_version`（登出/封禁/改密后旧令牌立即失效）。
3. **两者都没有** → `401 not authenticated`。

关键取舍：服务账号**复用同一个 `User` 主体**，不引入独立的“machine principal”实体。好处是所有下游权限判定（角色、可见 KB、审计 actor）无需为 API Key 单开一套分支——一把 Key 能做什么，完全等同于它 owner 能做什么。代价是 Key 不能拥有“比 owner 更小”的最小权限子集（无 scope 概念），属已知限制。

> 注意：因为 X-API-Key 解析出的也是 `User`，所以即便是受 `require_admin` 保护的端点（如 Webhook 管理），只要 API Key 的 owner 是 admin，用该 Key 也能调用——这是“服务账号=借用身份”模型的自然结果。

### 3.3 Webhook HMAC 签名算法与触发点

- **签名算法**：`webhook_service.sign(secret, body) = hmac.new(secret.encode(), body, sha256).hexdigest()`，即对**完整请求体字节**做 HMAC-SHA256，输出 64 位十六进制。接收方用同一 secret 重算并比对即可验证“来自 Lumen 且未被篡改”。
- **请求构造**：`dispatch()` 把事件序列化为 `{"event": <event>, "data": <payload>}`（`ensure_ascii=False`，UTF-8 字节），对所有 `active=true` 的 webhook 逐个 POST，带三个头：
  - `Content-Type: application/json`
  - `X-Lumen-Event: <event 名>`
  - `X-Lumen-Signature: <HMAC-SHA256 hex>`
- **触发点（共 2 个事件）**：
  - `page.updated` —— `controllers/wiki.py` 页面更新成功后，载荷 `{page_id, title, actor}`。
  - `page.commented` —— `controllers/comments.py` 评论创建成功后，载荷 `{page_id, title, actor}`。
  - 两处均在 `session.commit()` **之前**调用 `dispatch`，但 dispatch 自身吞掉所有异常（见 3.4），因此投递成败不影响该事务能否提交。

### 3.4 失败重试策略（实际：无重试，best-effort）

`dispatch()` 用 `httpx.AsyncClient(timeout=5)` 同步串行投递。每条投递包在 `try/except Exception` 里，**任何异常（连接失败、超时、非 2xx 抛出等）只记一条 `warning` 日志即放过**，注释明确写着「投递失败不影响主业务」。

这意味着：

- **没有重试**：失败即丢，无退避、无重投队列、无死信表。
- **不校验响应码**：未对返回状态做断言（`client.post` 不抛 4xx/5xx，除非显式 `raise_for_status`，此处未调用），因此接收方返回 500 也被视作“已投递”。
- **在请求线程内同步阻塞**：投递发生在 web 请求处理路径内（commit 前），最坏情况每个 webhook 阻塞至多 5 秒超时；若注册了大量慢 webhook 会拖慢写操作响应。

取舍理由：本期优先保证“主业务（编辑/评论）绝不因外部系统不可用而失败或回滚”，把可靠投递的复杂度（持久化队列 + 重试 + 死信）显式推迟。可靠投递列为未来工作（第 9 节）。

## 4. 数据模型变更

### 4.1 `api_keys`（迁移 `b991ece5479a_add_api_keys_table.py`，down_revision `8bfe1d1cf0fa`）

| 列 | 类型 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- |
| `id` | `Uuid` | PK，默认 `uuid4` | |
| `user_id` | `Uuid` | FK → `users.id`，索引 | 服务账号借用的 owner |
| `name` | `String(128)` | NOT NULL | 人类可读名（如 `ci-bot`） |
| `prefix` | `String(16)` | 索引 | UI 标识用（明文里的 `<prefix>` 段） |
| `key_hash` | `String(64)` | **unique**（`uq_api_keys_key_hash`）+ 索引 | `sha256(明文)`，校验依据 |
| `revoked` | `Boolean` | server_default `false` | 吊销标记（软删） |
| `created_at` | `DateTime(tz)` | server_default `now()` | |
| `last_used_at` | `DateTime(tz)` | nullable | 已建列，当前未回写（恒 NULL） |

索引：`ix_api_keys_user_id`、`ix_api_keys_prefix`。

### 4.2 `webhooks`（迁移 `d33d15cb9d99_add_webhooks_table.py`，down_revision `b991ece5479a`）

| 列 | 类型 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- |
| `id` | `Uuid` | PK，默认 `uuid4` | |
| `created_by` | `Uuid` | FK → `users.id` | 注册该 webhook 的 admin |
| `url` | `String(1024)` | NOT NULL | 投递目标 URL |
| `secret` | `String(64)` | NOT NULL | HMAC-SHA256 共享密钥 |
| `active` | `Boolean` | server_default `true` | 仅 active 的参与投递 |
| `created_at` | `DateTime(tz)` | server_default `now()` | |

两条迁移构成线性链：`8bfe1d1cf0fa` → `b991ece5479a`（api_keys）→ `d33d15cb9d99`（webhooks）。

## 5. API 端点

所有端点统一挂在 `/api` 前缀下（`main.py` 中 `include_router(..., prefix="/api")`）。

### 5.1 API Key（鉴权：任意已认证用户，作用于“当前用户自己的 Key”）

| 方法 | 路径 | 鉴权 / 权限 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/api-keys` | 已登录用户（JWT 或 X-API-Key） | 列出当前用户的 Key（`ApiKeyOut`，不含明文） |
| `POST` | `/api/api-keys` | 已登录用户 | 创建，返回 `ApiKeyCreated`（含一次性明文 `key`），记审计 `apikey.create`，`201` |
| `DELETE` | `/api/api-keys/{key_id}` | 已登录用户（仅限本人 Key，`get_owned` 校验归属，否则 `404`） | 吊销（置 `revoked=true`），记审计 `apikey.revoke`，`204` |

### 5.2 Webhook（鉴权：`require_admin`，整个 router 级依赖）

| 方法 | 路径 | 鉴权 / 权限 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/webhooks` | admin only | 列出全部 webhook（`WebhookOut`，**不回显 secret**） |
| `POST` | `/api/webhooks` | admin only | 注册（`WebhookCreate{url, secret}`），记审计 `webhook.create`，`201` |
| `DELETE` | `/api/webhooks/{webhook_id}` | admin only | 删除（硬删 `session.delete`），记审计 `webhook.delete`，找不到 `404`，成功 `204` |

> Webhook 没有“被外部调用”的入站端点；它只主动出站 POST 到第三方。第三方收到后用 `X-Lumen-Signature` 验签。

## 6. 权限与安全不变量

- **API Key 明文不可逆、不可二次读取**：库内仅 `sha256` 哈希；明文仅在 `POST /api-keys` 响应里出现一次，`ApiKeyOut`（列表/详情）无 `key` 字段。前端文案明确提示“仅创建时显示一次”。
- **Key 归属隔离**：吊销走 `api_key_repo.get_owned(key_id, user.id)`——只能吊销自己名下的 Key，对他人 Key 返回 `404`（不泄露存在性）。列表 `list_by_user` 同样按 `user_id` 过滤。
- **吊销 / 停用双重失效**：`resolve()` 要求 `revoked=false` 且 owner `is_active=true`。离职停用账号即同时切断该账号所有 API Key（无需逐把吊销）。
- **无效 Key 不回退 JWT**：带了 `X-API-Key` 但无效时直接 `401`，杜绝“伪 Key + 旧 JWT”的鉴权歧义。
- **Webhook secret 不回显**：`WebhookOut` 不含 `secret` 字段；测试 `test_webhook_crud_admin_only` 显式断言响应里 `"secret" not in r.json()`。
- **Webhook 管理仅限 admin**：router 级 `dependencies=[Depends(require_admin)]`，普通用户 `GET /api/webhooks` 得 `403`（测试覆盖）。
- **HMAC 防伪 / 防篡改**：出站每条带 `X-Lumen-Signature`，接收方验签可确认来源与完整性；secret 由 admin 注册时设定，长度约束 8–64 字符。
- **服务账号身份等同 owner（设计内不变量，非缺陷）**：API Key 能做的事 = owner 能做的事；权限不会因经由 Key 调用而扩大或缩小（无独立 scope）。

## 7. 配置项

本阶段**未引入任何新的环境变量 / 配置项**。

- API Key 的 prefix/secret 由 `secrets` 模块在运行时生成，无需配置。
- Webhook 的目标 URL 与 secret 是每条记录的数据库字段（运行期由 admin 通过 API 录入），不是部署级配置。
- `webhook_service.dispatch` 的超时（`httpx.AsyncClient(timeout=5)`）为代码内常量，当前**不可配置**。
- `core/config.py` 中既有的 `llm_api_key` 属 LLM 网关配置，与本阶段无关。

## 8. 测试覆盖

| 测试文件 | 关键用例 | 验证点 |
| --- | --- | --- |
| `api/tests/test_api_keys.py` | `test_api_key_create_use_revoke` | 创建返回明文且以 `lk_` 开头；用 `X-API-Key` 访问 `/api/me` 以 owner 身份通过；无效 Key → `401`；吊销后该 Key 立即 `401` |
| `api/tests/test_api_keys.py` | `test_no_auth_returns_401` | 既无 JWT 也无 API Key → `401`（双鉴权入口的兜底） |
| `api/tests/test_api_webhooks.py` | `test_sign_is_deterministic_hmac` | HMAC-SHA256 确定性（同输入同签名）、长度 64、换 secret 签名变化 |
| `api/tests/test_api_webhooks.py` | `test_dispatch_noop_without_webhooks` | 无注册 webhook 时 `dispatch` 不发起 HTTP、不抛异常 |
| `api/tests/test_api_webhooks.py` | `test_webhook_crud_admin_only` | admin 可增/查/删；响应不回显 `secret`；非 admin `GET` → `403` |

> 未覆盖：webhook 实际 HTTP 投递的成功/失败路径（无 mock server 用例）、`last_used_at` 回写（因功能未实现）。

## 9. 已知限制与未来工作

对照 IMPLEMENTATION_PLAN 阶段 8 的 ⬜ 项与本期取舍：

- **多租户隔离层（⬜，待拍板）**：仍单组织。是否做多客户 SaaS 硬隔离需确认目标部署形态（较大架构改造）。
- **更多数据源（⬜）**：docx/pptx/xlsx/html/网页抓取/Confluence 导入/OCR 均未做。
- **Webhook 可靠投递（本期取舍，待补）**：当前 best-effort 无重试。未来方向——投递落入持久化队列（项目已有 Redis + arq worker 基建可复用），加指数退避重试 + 死信表 + 投递日志，并把投递移出请求线程改为异步任务。
- **Webhook 事件面与前端管理（待补）**：当前仅 `page.updated` / `page.commented` 两类事件，且无前端 UI（只能调后端 admin API 管理）。未来可扩展事件类型（认证/晋升/删除等）并在设置页加 Webhook 管理界面。
- **API Key 增强（待补）**：无 scope/最小权限、无过期时间、`last_used_at` 未回写、无速率限额。
- **真实 PG 集成测试（⬜）**：消除 SQLite↔PG 漂移的集成测试未补。

> 订正说明：IMPLEMENTATION_PLAN 阶段 8 中「CI/CD 流水线」实际已标 ✅（GitHub Actions：后端 pytest + 前端 build/test，commit `9a9169a`），仅“真实 PG 集成测试”仍为 ⬜。任务下发描述把整条 CI/CD 列为未做，与计划文档及代码现状不符——以代码现状（CI/CD 已建）为准。

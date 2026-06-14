# 阶段 6:企业身份与数据治理 — as-built 设计文档

> 状态:as-built(已上线)· 日期:2026-06-14 · 方法论:superpowers(回溯补档)
> 对应 IMPLEMENTATION_PLAN 阶段 6 · 关联提交:
> `1dc1d9a`(自助改密+轮换会话) · `3a8b0e5`(管理员停用/启用) · `1211b4a`(登录失败锁定) ·
> `1aed799`(审计 CSV 导出) · `9278b84`(GDPR DSAR 个人数据导出) · `db95419`(refresh token + 前端静默续期)
> 说明:本组功能先开发后补档,本 spec 记录"实际建成"的设计与取舍(非事前计划)。

---

## 1. 背景与目标

LLM Wiki 在阶段 1-5 已具备内容创作、协作、检索与外部集成能力,但要进入 B 端企业采购流程,必须先跨过**身份与合规的硬门槛**——采购方安全问卷里的"必查项":会话能否被即时吊销、离职员工能否被即时切断、暴力破解是否有防护、审计日志能否导出留证、个人数据能否按 GDPR 自助导出。

阶段 6 的目标是用**最小、无状态友好**的实现补齐这批门槛项,而不引入重型身份基础设施(SSO/IdP/目录服务)。核心取舍是:

- 在保持 JWT **无状态**的前提下,用 `token_version` 这一单字段实现"软吊销",避免引入服务端会话存储(Redis session / 黑名单)。
- 登录失败锁定先用**进程内内存计数**落地,满足单实例部署的暴力破解防护,把"换 Redis 支持多实例"留作已知限制。
- 数据治理先交付**采购问卷最常见的两项**:审计 CSV 导出(合规留证)+ GDPR DSAR 个人数据自助导出(访问权),把删除权/保留策略/防篡改等更重的能力明确留作未来工作。

---

## 2. 范围

### ✅ 已建成(对照 IMPLEMENTATION_PLAN 阶段 6)

- **会话加固**
  - `token_version` 会话吊销:登出 / 改密 / 管理员停用时自增,使该用户所有存量 JWT 立即失效
  - `/auth/logout` 服务端登出(自增 token_version)
  - 自助改密 `/auth/change-password`:校验旧密码 → 更新 → 轮换其它会话 → 回签当前会话新令牌
  - 管理员停用 / 启用用户(`is_active`),停用同时吊销其所有会话(离职即时切断)
  - 登录失败锁定:同一邮箱 15 分钟内累计 5 次失败即锁定(返回 429)
  - refresh token:短访问令牌(8h)+ 长刷新令牌(7d),`/auth/refresh` 换新;前端 401 静默续期并重试一次
- **数据治理**
  - 审计日志 CSV 导出(admin 限定,可按 `action` 精确过滤,合规留证)
  - GDPR DSAR 个人数据自助导出 `/me/export`(数据主体访问权,导出资料 + 评论 + 收藏 + API Key 元数据)

### ⬜ 明确未做(留作后续阶段)

- refresh token 的**服务端撤销列表 / 旋转检测**(当前 refresh 仅靠 `token_version` 软吊销,不做一次性 rotation 重放检测)
- MFA(多因素认证)
- SSO(OIDC + SAML 2.0)、SCIM 2.0 用户 / 组 provisioning
- 细粒度自定义 RBAC + 资源级 ACL(KB / 页级共享、自定义角色)——当前仅有 `admin` / `user` + 团队只读成员
- 被遗忘权(个人数据删除)、数据保留策略、备份恢复
- 审计防篡改(哈希链 / WORM 存储 / 签名)

---

## 3. 架构与关键设计决策

### 3.1 分层落点

| 关注点 | 落点 | 文件 |
|---|---|---|
| JWT 编解码(含 `tv` / `type` / `exp`) | core | `app/core/security.py` |
| 鉴权依赖(校验 `is_active` + `tv`)、`require_admin` | core | `app/core/deps.py` |
| 登录失败锁定计数、认证 | service | `app/services/auth_service.py` |
| 审计事件记录 / 查询 | service | `app/services/audit_service.py` |
| 用户读写(改密 / 停用 / 自增 token_version) | repo | `app/repositories/user_repo.py` |
| 登录 / 登出 / 刷新 / 改密 / me / 个人数据导出 | controller | `app/controllers/auth.py` |
| 停用 / 启用用户 | controller | `app/controllers/org.py` |
| 审计列表 / CSV 导出 | controller | `app/controllers/audit.py` |
| User 模型(`token_version` / `is_active`) | model | `app/models/user.py` |

### 3.2 关键设计决策

**决策一:无状态 JWT + `token_version` 软吊销。**
JWT 一经签发在过期前天然有效,无法服务端撤销。为获得"立即失效"能力而不引入服务端会话存储,在 `users` 表加一列 `token_version`,签发令牌时把当前版本写入 payload 的 `tv` 字段;鉴权时(`deps.get_current_user`)比对 `payload["tv"]` 与库内 `user.token_version`,不一致即 401。任何需要"踢掉存量会话"的动作(登出 / 改密 / 停用)只需 `bump_token_version` 自增一次。代价是每次鉴权都要查一次用户行,但本就需要查行取 `role` / `is_active`,无额外开销。

**决策二:改密"轮换其它会话、保当前会话"。**
`/auth/change-password` 自增 `token_version` 会让**包括当前请求所用令牌在内**的全部令牌失效,因此改密成功后立即用最新版本回签一个新 access token 返回前端,实现"改密后其它设备掉线、当前设备无感"的体验。这一行为有测试 `test_change_password_rotates_sessions` 锁定:旧令牌改密后 401,返回的新令牌可用。

**决策三:停用即吊销。**
管理员停用用户走两步——`set_active(False)` + `bump_token_version`。前者让后续任何鉴权(以及重新登录)被拒(`deps` 校验 `is_active`),后者立即作废其已签发令牌,二者叠加保证"离职即时切断、且重新登录也进不来"。`test_admin_deactivate_blocks_user_then_activate` 覆盖:停用后旧令牌 401、重新登录拿到的令牌也 401、启用后可正常登录。另含安全护栏:**管理员不能停用自己**(400)。

**决策四:登录失败锁定先用进程内内存。**
`auth_service` 维护模块级字典 `_fails: dict[email -> list[timestamp]]`,`is_locked` 仅统计落在 `_WINDOW`(900s)内的失败次数,达到 `_MAX_FAILS`(5)即锁定。登录成功 `clear_failures` 清零。锁定命中时即使密码正确也返回 429。选用内存而非 Redis 是务实取舍:单实例部署即可用,代码零外部依赖;明确把"多实例需换 Redis"记为已知限制(见 §9)。`reset_lockout()` 供测试隔离用。

**决策五:refresh token 用 `type` 字段区分,沿用 `token_version` 校验。**
access 与 refresh 共用 HS256 与同一 `jwt_secret`,refresh token 的 payload 多带 `type=refresh` 且有效期更长(7d vs 8h)。`/auth/refresh` 显式校验 `type == "refresh"`(防止 access 当 refresh 用)、`is_active`、以及 `tv == user.token_version`(登出 / 改密 / 停用同样会作废 refresh)。前端(`web/src/api/client.ts`)在收到 401 时用 refresh 静默续期、并发去重、成功后重试一次原请求。

```
登录                         ┌─ access  (8h, {sub, tv, exp})
  authenticate ── 签发 ──────┤
                             └─ refresh (7d, {sub, tv, type:refresh, exp})

鉴权 get_current_user:
  decode → 查 user → is_active? → payload.tv == user.token_version?  → 放行 / 401

吊销(登出 / 改密 / 停用):
  bump_token_version  →  库内 tv+1  →  所有存量 access & refresh 的 tv 不再匹配 → 全部失效
```

---

## 4. 数据模型变更

阶段 6 在既有 `users` 表上新增两列(均经 `alembic revision` 生成迁移骨架,`server_default` 保证存量行平滑回填):

| 列名 | 类型 | 约束 / 默认 | 含义 | 迁移文件 |
|---|---|---|---|---|
| `token_version` | `Integer` | `NOT NULL`,`server_default="0"` | 会话版本;登出 / 改密 / 停用时自增,使存量 JWT 失效 | `1245f96cd622_add_user_token_version.py` |
| `is_active` | `Boolean` | `NOT NULL`,`server_default=true` | 账号是否启用;停用即拒绝鉴权与登录 | `8bfe1d1cf0fa_add_user_is_active.py` |

审计导出复用既有 `audit_events` 表(`app/models/audit_event.py`,迁移 `264d68a888c5_audit_events`,本阶段**未改其结构**),字段:`id` / `actor_id`(FK users) / `action` `String(64)` / `target_type` `String(32)` / `target_id` `Uuid` / `detail` `JSON` / `created_at`(timezone,索引)。

GDPR 导出**不新增任何表 / 字段**,纯读聚合现有 `users` / `comments` / `favorites` / `api_keys`。

---

## 5. API 端点

路由统一挂在 `/api` 前缀下。鉴权列说明:`Bearer`= 需登录令牌;`Bearer admin`= 需 admin 角色(`require_admin`);`匿名`= 无需令牌。

| 方法 | 路径 | 鉴权 / 权限 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 匿名 | 登录;锁定中返回 429,凭据错误返回 401 并记一次失败 |
| POST | `/auth/refresh` | 匿名(凭 refresh token) | 校验 `type`/`is_active`/`tv`,换发新 access + refresh |
| POST | `/auth/logout` | `Bearer` | 自增 `token_version`,作废本人全部令牌;返回 204 |
| POST | `/auth/change-password` | `Bearer` | 旧密码错误 400;成功轮换其它会话并回签当前会话新令牌 |
| GET | `/me` | `Bearer` | 当前用户资料(`UserOut`) |
| GET | `/me/export` | `Bearer` | GDPR DSAR:导出本人 profile + 评论 + 收藏 + API Key 元数据 |
| POST | `/users/{user_id}/deactivate` | `Bearer admin` | 停用用户并吊销其会话;停用自己返回 400,用户不存在 404 |
| POST | `/users/{user_id}/activate` | `Bearer admin` | 重新启用用户;用户不存在 404 |
| GET | `/audit` | `Bearer admin` | 审计列表(分页 envelope + 总数 + `action` 过滤) |
| GET | `/audit/export` | `Bearer admin` | 审计 CSV 导出(可按 `action` 过滤,合规留证) |

`TokenResponse` 形状:`{ access_token, refresh_token?(改密返回 null), token_type="bearer" }`。

审计 CSV 表头:`created_at,actor_email,action,target_type,target_id,detail`;`Content-Type: text/csv; charset=utf-8`;`Content-Disposition: attachment; filename=audit_log.csv`;单次最多导出 10000 行。

`/me/export` 响应结构:
```json
{
  "profile":  { "id", "email", "display_name", "role" },
  "comments": [ { "page_id", "body", "created_at" } ],
  "favorites":[ { "page_id", "title" } ],
  "api_keys": [ { "name", "prefix", "revoked" } ]
}
```
注:API Key 仅导出元数据(name / prefix / revoked),**不导出密钥明文或哈希**。

---

## 6. 权限与安全不变量

- **会话即时吊销**:登出 / 改密 / 停用任一动作后,该用户全部存量 access 与 refresh 令牌在下一次鉴权时即被拒(`tv` 比对)。无状态 JWT 由此获得"撤销"语义。
- **停用即拒绝**:`is_active=False` 的用户既无法用存量令牌(`deps` 拦截),也无法重新登录通过(`authenticate` 取出的用户在鉴权阶段被 `is_active` 拦)。
- **自我保护**:管理员不能停用自己(400),避免误操作把自己锁在系统外。
- **暴力破解防护**:同邮箱 15 分钟内 5 次失败即锁定 15 分钟窗口,锁定期间即使凭据正确也拒绝(429)。
- **令牌类型隔离**:access token 不能当 refresh 用(`/auth/refresh` 校验 `type=="refresh"`),反之 access 鉴权路径不依赖 `type`。
- **审计访问最小面**:`/audit` 与 `/audit/export` 整个路由 `dependencies=[Depends(require_admin)]`,非 admin 一律 403。
- **个人数据脱敏**:DSAR 导出只含本人数据(以 `get_current_user` 为主体过滤),API Key 不泄露密钥物料。
- **密码存储**:bcrypt 加盐哈希(`hash_password`/`verify_password`),改密前必须验证旧密码。

---

## 7. 配置项

阶段 6 涉及的配置集中在 `app/core/config.py`(环境变量名为大写形式):

| 配置 / 环境变量 | 默认值 | 含义 |
|---|---|---|
| `jwt_secret` / `JWT_SECRET` | `"change-me-in-prod"`(弱默认) | JWT 签名密钥;非 dev/test/local 环境若仍为弱默认或长度 < 32 则**拒绝启动** |
| `jwt_expire_min` / `JWT_EXPIRE_MIN` | `480`(8h) | access token 有效期;配合 `token_version` 吊销 |
| `refresh_expire_min` / `REFRESH_EXPIRE_MIN` | `10080`(7d) | refresh token 有效期 |

**注意**:登录失败锁定阈值与窗口**不是配置项**,而是 `app/services/auth_service.py` 内的模块常量 `_MAX_FAILS=5`、`_WINDOW=900`(秒)。如需可调,需后续提升为配置(见 §9)。JWT 算法固定为 `HS256`(`security.ALGORITHM`)。

---

## 8. 测试覆盖

| 测试文件 | 关键用例 | 覆盖点 |
|---|---|---|
| `api/tests/test_api_auth.py` | `test_login_and_me` | 登录 + `/me` 基线 |
| | `test_logout_revokes_existing_token` | 登出后旧令牌 401(token_version 吊销) |
| | `test_refresh_token_issues_new_access` | refresh 换新 access;access 当 refresh 用被拒 401 |
| | `test_change_password_rotates_sessions` | 旧密码错误 400;改密后旧令牌 401、新令牌可用、新密码可登录 |
| | `test_login_lockout_after_repeated_failures` | 5 次失败后即使密码正确也 429 |
| | `test_me_export_returns_personal_data` | DSAR 导出含 profile / 评论 / 收藏 |
| | `test_login_bad_password` | 错误密码 401 |
| `api/tests/test_security.py` | `test_password_roundtrip` / `test_jwt_roundtrip` | bcrypt 往返、JWT 编解码 `sub` |
| `api/tests/test_api_audit.py` | `test_admin_action_recorded_and_listed` | 通过 API 建用户产生审计事件并可列出 |
| | `test_audit_pagination_and_filter` | 分页(limit/total)+ `action` 过滤 |
| | `test_audit_csv_export` | CSV 表头与内容、`text/csv` Content-Type |
| | `test_non_admin_cannot_view_audit` | 非 admin 访问审计 403 |
| `api/tests/test_api_org.py` | `test_admin_deactivate_blocks_user_then_activate` | 停用后旧令牌/重登均 401、停用自己 400、启用后可登录 |

前端侧:`web/src/pages/SettingsPage.tsx`(修改密码 + GDPR 导出按钮)、`web/src/pages/AdminPage.tsx`(停用/启用 + 已停用徽章)、`web/src/api/client.ts`(401 静默续期、并发去重、重试一次)。

---

## 9. 已知限制与未来工作

对照 roadmap 阶段 6 的 ⬜ 项与本阶段实现取舍:

- **登录锁定为进程内内存**:多实例 / 水平扩容下各进程计数独立,防护被稀释;且进程重启计数清零。规模化需迁移到 Redis,并把 `_MAX_FAILS`/`_WINDOW` 提升为配置项。
- **refresh token 无服务端 rotation / 重放检测**:当前仅靠 `token_version` 软吊销,未做一次性刷新令牌与重放检测;refresh token 失窃在 `token_version` 未变期间仍可用。
- **审计无防篡改**:`audit_events` 为普通可写表,无哈希链 / WORM / 签名;满足"留证导出"但不满足"不可抵赖"。
- **数据治理仅访问权**:已交付 GDPR 访问权(导出),未做被遗忘权(删除)、保留策略、备份恢复。
- **身份联邦缺位**:无 MFA、无 SSO(OIDC/SAML)、无 SCIM provisioning。
- **授权粒度粗**:仅 `admin`/`user` + 团队只读成员;无自定义角色、无 KB/页级资源 ACL。

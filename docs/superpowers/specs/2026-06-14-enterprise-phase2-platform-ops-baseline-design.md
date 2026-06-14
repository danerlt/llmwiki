# 阶段 2:平台基线与可运维性 — as-built 设计文档

> 状态:as-built(已上线)· 日期:2026-06-14 · 方法论:superpowers(回溯补档)
> 对应 IMPLEMENTATION_PLAN 阶段 2 · 关联提交:
> `141e3e1`(安全/运维中间件 CORS+安全头+request_id + 全局异常处理 + 深度健康检查 readyz)、
> `a3d19fe`(结构化日志带 request_id + 请求访问日志)、
> `0e4cd3b`(Prometheus /metrics 请求量+延迟)、
> `cd3d1a9`(LLM 网关健壮化 超时+429/5xx/超时退避重试+4xx 不重试+token 计量)、
> `275d2e6`(审计分页 envelope+总数+动作过滤 + 前端加载更多)、
> `4c4c68b`(API 限流中间件 每 IP 每分钟固定窗口,默认关闭可配)、
> `72dffae`(TrustedHost 中间件,防 Host 头注入,按需开启)、
> `1aed799`(审计 CSV 导出,合规留证)、
> `fcd3c29` / `dc609c6` / `50a39d2`(计划进度标记)。
> 说明:本组功能先开发后补档,本 spec 记录"实际建成"的设计与取舍(非事前计划)。

---

## 1. 背景与目标

阶段 1 交付了核心业务闭环(登录/组织/KB/摄入/检索问答),但缺一层企业采购"必查项"——安全响应头、统一错误体、请求可追踪、限流、深度健康检查、指标曝光、上游 LLM 调用的健壮化。这些不是产品功能,而是**让产品能被企业放心买进来、放进生产、被运维团队接住**的地基。

本阶段目标:在不引入重型依赖(无 prometheus_client、无 slowapi 等)的前提下,用一组轻量中间件 + 一个全局异常 handler + 两个健康端点 + 一个进程内指标模块 + LLM 客户端内置重试,补齐 Web/运维基线。所有能力作为"地基"贯穿后续一切特性。

设计取舍的总基调:**够用即可、零额外依赖、显式可配、探针路径豁免**。多实例横向扩展时的全局一致性(限流共享存储、指标跨进程聚合)有意延后,代码注释中显式标注了升级路径。

## 2. 范围

### 2.1 ✅ 已建成

- **安全/运维中间件**:四项安全响应头(`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` / `X-XSS-Protection`)+ CORS + `X-Request-ID` 生成/透传并贯穿日志与异常体。
- **API 限流**:每 IP 每分钟固定窗口,进程内计数,默认关闭(`rate_limit_per_min<=0`),探针路径与 `OPTIONS` 预检豁免,超限返回 429 + `Retry-After: 60`。
- **TrustedHost**:仅在显式配置 `allowed_hosts` 时启用的 Host 头白名单(防 Host 头注入)。
- **全局异常处理**:兜底未捕获 `Exception`,完整堆栈进服务端日志,对外只返回 `{"detail": "internal server error", "request_id": ...}`,不泄漏堆栈/SQL/内部细节。
- **结构化日志 + 请求访问日志**:根日志格式带 `[request_id]`;每个请求记录 `method path -> status dur(ms)`。
- **深度健康检查**:`/api/health`(存活)+ `/api/readyz`(探 DB/Redis/MinIO,任一不通 503)。
- **Prometheus `/metrics`**:请求量(按 method+status)、延迟聚合、LLM 调用数、LLM token 计量。
- **审计接口统一分页**:`Paginated` envelope(items+total+limit+offset)+ 动作过滤 + 前端"加载更多"。
- **LLM 网关健壮化**:可配超时;对瞬时网络错误与 429/5xx 指数退避重试;4xx 不重试;成功响应记录 token 用量到 metrics。

### 2.2 ⬜ 明确未做(对照 IMPLEMENTATION_PLAN)

- ⬜ **队列积压指标**:metrics 暂未曝光 arq 队列深度/积压。
- ⬜ **pages/sources 分页**:仅审计接口落地了 `Paginated` envelope;wiki pages / sources 列表仍受 KB 体量约束暂留全量返回(计划中标记为 🚧 部分完成)。
- ⬜ **LLM 熔断**:仅有重试退避,无熔断器(连续失败后快速失败 + 半开恢复)。

## 3. 架构与关键设计决策

### 3.1 中间件装配顺序(`main.py::create_app`)

FastAPI/Starlette 的 `add_middleware` 后加者在外层。实际装配顺序与执行顺序如下:

```
请求 →  TrustedHost(最外, 仅当配置 allowed_hosts)
     →  RateLimitMiddleware
     →  RequestContextMiddleware   ← 生成/透传 request_id、计时、写访问日志、补安全头
     →  CORSMiddleware(最内)
     →  路由处理
```

关键取舍:`RequestContextMiddleware` 故意放在 `CORSMiddleware` 外层,使 **request_id 最先设置、安全头最后补**,响应离开时一定带上这两组头;CORS 作为最内层只管跨域协商。`request_id` 通过 `ContextVar`(`request_id_ctx`)而非线程局部存储传递,契合 asyncio 单线程多协程模型,供日志格式化与异常 handler 无侵入读取。

### 3.2 分层落点

| 关注点 | 落点 | 说明 |
|---|---|---|
| 安全头 / CORS / request_id / 限流 | `core/middleware.py` | `RateLimitMiddleware`、`RequestContextMiddleware`、`request_id_ctx` |
| TrustedHost | `main.py` 装配 Starlette `TrustedHostMiddleware` | 按需 |
| 全局异常 handler | `main.py::create_app` 内 `@app.exception_handler(Exception)` | **无独立 exceptions.py** |
| 结构化日志 / 访问日志 | `core/logging.py`(格式)+ `middleware.py`(访问日志发射) | logger `app.access` |
| Prometheus 指标 | `core/metrics.py`(进程内聚合)+ `controllers/health.py`(曝光) | 无第三方依赖 |
| 健康检查 | `controllers/health.py` | `/health` `/readyz` `/metrics` |
| LLM 网关 | `integrations/llm.py::LLMClient` | 重试退避内嵌于 `complete()` |
| 审计分页 | `controllers/audit.py` + `schemas/common.py::Paginated` + `services/audit_service.py` + `repositories/audit_repo.py` | repo 层支持 `limit/offset/action` + `count` |
| 配置开关 | `core/config.py::Settings` | 限流阈值、CORS、Host 白名单 |

### 3.3 限流:进程内固定窗口

`RateLimitMiddleware` 用 `dict[(ip, minute_window), count]` 做固定窗口计数。每次请求按 `int(time.time()) // 60` 算窗口,先清理非当前窗口键(避免无界增长),再自增计数,超 `rate_limit_per_min` 返回 429。

- **默认关闭**:`rate_limit_per_min` 默认 0,`<=0` 直接放行——生产按需开启,避免本地/测试误触发。
- **超限响应**:返回 `429` + `Retry-After: 60`,响应体为 `{"detail": "请求过于频繁，请稍后再试"}`。注意:此 detail 是**中文**面向终端用户的可读文案,而全局异常 handler 的 500 detail 是英文 `internal server error`(见 3.4 节)——前者属用户可直接看到的限流提示(故用中文),后者刻意保持泛化以不泄漏内部细节;两处语言风格不统一是有意取舍而非疏漏,后续若要统一文案需一并评估面向用户与面向运维的不同诉求。
- **豁免**:`OPTIONS`(CORS 预检)与探针路径 `/api/health` `/api/readyz` `/api/metrics`(`_RL_EXEMPT`)不计入,保证健康检查与监控不被限流误杀。
- **多实例局限**:进程内计数,多副本下各自独立。注释明确"多实例需换 Redis"。
- 提供 `reset_rate_limit()` 供测试清空计数。

### 3.4 全局异常处理:不泄漏内部细节

`@app.exception_handler(Exception)` 兜底所有未被业务捕获的异常:
- `_error_logger.exception(...)` 把**完整堆栈 + request_id + method + path** 写进服务端日志;
- 对外返回 `status_code=500`、`{"detail": "internal server error", "request_id": rid}`——只给一个可供用户报障/运维回查的 request_id,**绝不外泄堆栈、SQL、ORM 内部信息**。

这是企业渗透测试与安全审计的高频查项:错误响应不得回显内部实现。

### 3.5 指标:零依赖进程内聚合

`core/metrics.py` 用模块级变量 + `threading.Lock` 维护四类计数,`render()` 按 Prometheus 文本曝光格式(`# HELP` / `# TYPE` + 样本行)输出:
- `http_requests_total{method,status}`(counter)——`RequestContextMiddleware` 每请求 `observe()`;
- `http_request_duration_seconds`(summary:`_sum` + `_count`)——同上;
- `llm_calls_total`(counter)、`llm_tokens_total`(counter)——`LLMClient` 每次调用 `observe_llm(tokens)`。

取舍:不引 `prometheus_client`,避免新依赖;多进程部署时各进程独立计数,由 Prometheus 按实例 label 聚合(注释已说明)。

### 3.6 LLM 网关健壮化

`LLMClient.complete()` 实现重试循环(`integrations/llm.py`):
- 可配 `timeout`(默认 120s)、`max_retries`(默认 2)、`backoff_base`(默认 0.5s);
- **可重试**:瞬时网络错误(`httpx.TimeoutException` / `httpx.TransportError`)与 HTTP `429` / `>=500`;
- **不重试**:其它 4xx(鉴权/请求错误,重试无意义)立即抛出;
- 退避:第 `attempt` 次失败后 `sleep(backoff_base * 2**attempt)`(指数退避);
- 成功响应解析 `usage.total_tokens` 调 `metrics.observe_llm()` 记 token;流式 `stream()` 无 usage 回传,仅记调用次数(`observe_llm(0)`)。
- `transport` 参数支持注入 `httpx.MockTransport`,便于在测试中模拟 5xx/4xx(依赖注入而非打桩)。
- **重试仅覆盖 `complete()`**:上述退避重试循环只包裹非流式 `complete()`;流式 `stream()` 直接打开连接并 `raise_for_status()`,**不走 `max_retries` 包裹**——上游瞬时错误(超时/429/5xx)不会自动重试,失败中途即抛出由调用方收尾(SSE 已开始逐块下发,中途重试会破坏增量语义)。即流式与非流式的健壮化语义不同,使用流式接口的上游需自行处理瞬时失败。
- **提示注入防护**:`_messages()` 拼装历史时会过滤掉非 `user`/`assistant` 角色的消息(`integrations/llm.py` 第 44–46 行,仅保留 `role in ("user","assistant")` 且 `content` 为非空字符串者),防止历史中夹带的 `system`/其它角色被注入到提示中改写指令(由 `test_llm_messages_includes_history_and_filters_bad_roles` 覆盖)。

## 4. 数据模型变更

**本阶段无新增表/字段。**

阶段 2 的"审计接口统一分页"复用既有的 `audit_events` 表(该表在更早的审计阶段由迁移 `264d68a888c5_audit_events` 引入),阶段 2 只在 **应用层**新增了分页/计数/动作过滤能力(`audit_repo.count` + `list_recent` 的 `offset/action` 参数 + `Paginated` envelope),未触碰 schema。

`audit_events` 既有结构(仅作背景,非本阶段产物):

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Uuid | 主键,默认 uuid4 |
| `actor_id` | Uuid | FK → `users.id` |
| `action` | String(64) | 动作标识,如 `user.create` |
| `target_type` | String(32) | 可空 |
| `target_id` | Uuid | 可空 |
| `detail` | JSON | 可空 |
| `created_at` | DateTime(tz) | server_default now(),带索引 |

## 5. API 端点

| 方法 | 路径 | 鉴权/权限 | 说明 |
|---|---|---|---|
| GET | `/api/health` | 公开 | 存活探针,恒返回 `{"status":"ok"}` |
| GET | `/api/readyz` | 公开 | 就绪探针,探 DB/Redis/MinIO,任一不通 503,返回 `{"ready":bool,"checks":{db,redis,minio}}` |
| GET | `/api/metrics` | 公开 | Prometheus 文本(`text/plain; version=0.0.4; charset=utf-8`) |
| GET | `/api/audit` | **admin**(`require_admin`) | 分页审计列表,`Paginated[AuditEventOut]`,查询参 `limit`(1–200,默认 50)/`offset`(≥0)/`action`(精确过滤) |
| GET | `/api/audit/export` | **admin** | 审计 CSV 导出(合规留证),可按 `action` 过滤,`attachment; filename=audit_log.csv` |

说明:
- 三个探针端点公开且被限流豁免,以保证 K8s/LB 探活、Prometheus 抓取不受鉴权与限流影响。
- `/api/audit*` 整个 router 通过 `dependencies=[Depends(require_admin)]` 强制管理员,非 admin 返回 403。
- 所有响应(含上述端点)经 `RequestContextMiddleware` 统一补 `X-Request-ID` 与四项安全头。

## 6. 权限与安全不变量

- **错误不泄漏**:500 响应只含 `detail` + `request_id`,堆栈/SQL 只进服务端日志。安全审计硬不变量。
- **审计仅管理员**:`/api/audit` 与 `/api/audit/export` 均受 `require_admin` 保护,普通用户 403(`test_non_admin_cannot_view_audit` 验证)。
- **探针无敏感信息**:`/readyz` 只回各依赖通/不通的布尔,不回连接串、版本、内部地址。
- **Host 头注入防护**:配置 `allowed_hosts` 后,非白名单 Host 被 `TrustedHostMiddleware` 拒绝。
- **安全响应头**:`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`(防点击劫持)、`Referrer-Policy: no-referrer`、`X-XSS-Protection: 0`(显式关闭旧版浏览器有缺陷的过滤器,遵循 OWASP 现行建议)。
- **CORS 凭据**:`allow_credentials=True` + 显式来源白名单(`cors_origin_list`,留空回退 `[app_url]`),`expose_headers=["X-Request-ID"]` 使前端可读取追踪 id。
- **限流**:开启后按 IP 阻断暴力/爬取,探针豁免避免误伤监控。
- **请求可追踪**:request_id 贯穿响应头 + 每条日志 + 错误体,支持端到端排障与合规取证关联。
- **LLM 历史角色过滤(防提示注入)**:`LLMClient._messages()` 拼装对话历史时只接纳 `user`/`assistant` 角色且内容为非空字符串的消息,丢弃 `system` 及任何其它角色——防止持久化历史里夹带的恶意/异常角色被回灌进提示、篡改系统指令。系统提示恒由本端在数组首位注入,历史不得越权改写(`test_llm_messages_includes_history_and_filters_bad_roles` 验证)。

## 7. 配置项

均为 `core/config.py::Settings` 字段,通过环境变量(字段名大写)注入。

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `RATE_LIMIT_PER_MIN` | `0` | 每 IP 每分钟请求上限,`<=0` 关闭限流(生产按需开启) |
| `ALLOWED_HOSTS` | `""` | 逗号分隔的允许 Host;留空则不启用 TrustedHost 校验 |
| `CORS_ORIGINS` | `""` | 逗号分隔的允许跨域来源;留空回退到 `[APP_URL]` |
| `APP_URL` | `http://localhost` | 前端站点 URL;CORS 留空时的默认来源 |
| `APP_ENV` | `dev` | 仅 `dev`/`test`/`local` 允许弱默认凭据,其它一切值(含 prod/staging/拼写错误/漏设)按生产严格处理 |

LLM 网关相关运行参数(`timeout`/`max_retries`/`backoff_base`)目前作为 `LLMClient` 构造参数存在(默认 120s / 2 次 / 0.5s),尚未提升为独立环境变量。

> 说明:截至本次补档,`.env.example` 仅列出了阶段 1 的配置项,**未补充** `RATE_LIMIT_PER_MIN`/`ALLOWED_HOSTS`/`CORS_ORIGINS`/`APP_ENV`。这些字段在 `Settings` 中真实存在且可经环境变量覆盖,只是文档样例未同步(见第 9 节与 self-review)。

## 8. 测试覆盖

| 测试文件 | 关键用例 |
|---|---|
| `api/tests/test_health.py` | `test_health_ok`(存活)、`test_response_has_request_id_and_security_headers`(自动生成 request_id + nosniff/DENY)、`test_incoming_request_id_is_propagated`(透传入站 X-Request-ID)、`test_access_log_emitted_with_method_and_path`(访问日志含方法/路径)、`test_rate_limit_returns_429`(超阈 429,限流在鉴权前)、`test_metrics_exposes_request_counters`(`http_requests_total` + `_duration_seconds_count`)、`test_readyz_ok_when_all_deps_up`(全通 200)、`test_readyz_503_when_dep_down`(任一不通 503 + 标出失败依赖) |
| `api/tests/test_config.py` | `test_settings_defaults`、`test_prod_rejects_weak_default_secrets`(prod 弱默认拒启)、`test_prod_accepts_strong_secrets`、`test_allowed_and_cors_host_parsing`(逗号分隔解析 + 留空回退)、`test_dev_keeps_defaults_usable`、`test_nondev_env_rejects_weak_secrets`(staging/production/prd/空/PROD 全拒)、`test_dev_weak_secret_warns`(dev 告警) |
| `api/tests/test_integrations_contract.py` | `test_llm_client_constructs`、`test_llm_messages_includes_history_and_filters_bad_roles`(历史拼装 + 过滤非 user/assistant 角色防注入)、`test_llm_retries_on_5xx_then_succeeds`(503 后重试成功,calls==2)、`test_llm_does_not_retry_on_4xx`(400 立即抛,calls==1) |
| `api/tests/test_api_audit.py` | `test_admin_action_recorded_and_listed`(动作产生审计 + envelope 含 total/items)、`test_audit_pagination_and_filter`(`limit=2` 截断 + `total` 反映全量 + `action` 过滤)、`test_audit_csv_export`(CSV 头 + 内容)、`test_non_admin_cannot_view_audit`(403) |

## 9. 已知限制与未来工作

对照 roadmap 阶段 2 的 ⬜/🚧 项:

1. **队列积压指标(⬜)**:`/metrics` 未曝光 arq 队列深度;运维无法直接看到积压。后续可在 metrics 增 `queue_pending` gauge。
2. **pages/sources 分页(🚧)**:`Paginated` envelope 仅落地审计;wiki pages / sources 列表仍全量返回,受单 KB 体量约束暂留。复用 `schemas/common.py::Paginated` 即可推广。
3. **LLM 熔断(⬜)**:仅有重试退避,无熔断器;上游持续故障时仍会逐请求重试。
4. **限流多实例一致性**:进程内固定窗口,多副本下不共享;真要全局限流需迁到 Redis(代码注释已标注)。
5. **指标多进程聚合**:进程内计数,需 Prometheus 按实例 label 聚合;无 histogram 桶(延迟仅 sum/count summary)。
6. **LLM 网关参数未配置化**:`timeout`/`max_retries`/`backoff_base` 仍是构造参数,未提升为环境变量。
7. **`.env.example` 未同步**:阶段 2 新增的 `RATE_LIMIT_PER_MIN`/`ALLOWED_HOSTS`/`CORS_ORIGINS`/`APP_ENV` 未补进样例文件(功能已实现,仅文档缺口)。

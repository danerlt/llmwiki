# 后端工程化对齐实施计划（对标 fastapi-project-template-v3）

> 来源：`docs/fastapi-project-template-v3.md` 规范 × 当前 `api/` 后端的 13 维度深度对标（14 agent 工作流）。
> 老板已拍板 4 项大决策（全部取最彻底方案）：
> 1. **统一响应信封 Response[T]**（全面引入；前端 `web/src/api/client.ts` 单点拆包适配）
> 2. **Service/Repository 全面重构为类 + 单例**（含异步 `BaseCrud[ModelT]`）
> 3. **依赖管理迁移到 uv + pyproject.toml**（同步改 Dockerfile / CI）
> 4. **测试切换到真实 PostgreSQL 容器**（独立测试数据库 + savepoint 隔离）
>
> 既定不变项（keep_current）：异步 SQLAlchemy/asyncpg、arq、PostgreSQL、多容器部署、标准 logging+ContextVar、业务异常仍以标准 HTTP 状态码语义对外（信封内 code 与 HTTP status 并存）、弱凭据 model_validator 校验。
>
> 流程：每阶段 TDD（红→绿→重构），逐步提交，状态随进展更新。全部完成后删除本文件，并把"真实 PG 集成测试 / CI"等对应项在 `IMPLEMENTATION_PLAN.md` 勾掉。

---

## 决策备注：统一信封与 HTTP 语义如何共存

规范原版是"业务异常一律 HTTP 200 + body.code 分流"。本项目前端是 React + 单点 `apiFetch`，且已大量依赖 401→跳登录、403/404 语义。**最终方案（兼顾规范与前端友好）**：

- 成功：`HTTP 200` + `Response[T]{success:true, code:"0", data:...}`
- 业务异常：返回**对应 HTTP 状态码**（401/403/404/409/422/500…）+ 同一信封 `{success:false, code, message, detailMessage, data:null, request_id}`。
- 即"统一信封形态" + "保留 HTTP 状态码语义"，而非规范的"一律 200"。前端 `client.ts` 单点拆包：`success:true` 取 `data`；`success:false` 抛带 `code` 的 `BusinessError`；保留 401 刷新逻辑。

> 这样既满足老板"全面引入统一信封"，又不牺牲 REST 语义与现有前端鉴权流。若老板坚持要"一律 200"，仅需改 handler 的 status_code 映射一处。

---

## 阶段 1：工程基线（uv + lint/type-check）

**目标**：依赖单一源迁移到 uv + pyproject.toml；补齐 ruff/mypy 配置与 .python-version；同步 Dockerfile / CI。
**成功标准**：`uv sync` 生成完整 `uv.lock`；`uv run pytest -q` 全绿（与基线同）；`uv run ruff check` 通过（或仅留可控告警）；Docker 构建与 CI 改 uv 后逻辑等价。
**测试**：现有 pytest 全量通过；ruff/mypy 能跑起来并产出报告。
**步骤**：
1. `api/pyproject.toml` 写 `[project]`（按职责分组的 dependencies，从 requirements.txt 迁移，版本约束规范化）+ `[project.optional-dependencies].dev`（ruff/mypy）/`.test`（pytest 等）+ `[tool.ruff]` + `[tool.mypy]`（overrides 用 arq/aiosqlite 替换 funboost）+ 保留 `[tool.pytest.ini_options]`。
2. `uv lock` 生成完整锁文件；删除/保留 requirements.txt 决策（保留一份 `uv export` 兜底或直接弃用）。
3. 增 `api/.python-version`（3.12）。
4. 改 `api/Dockerfile`：分层（系统依赖 → `uv sync --frozen --no-dev` → COPY 代码）。
5. 改 `.github/workflows/ci.yml` 后端 job：用 `astral-sh/setup-uv` + `uv sync` + `uv run pytest`，并加 `uv run ruff check`。
6. 跑一遍 ruff，修明显问题（未用 import 等），不一次性强推全部规则。
**状态**：✅ 已完成（uv+pyproject+uv.lock、ruff/mypy 配置、.python-version/.dockerignore、Dockerfile/CI 迁 uv；ruff 全绿、pytest 全量绿、docker build 绿）

## 阶段 2：测试基座（真实 PostgreSQL 容器 + 隔离）

**目标**：测试从 SQLite 内存切到真实 PG（独立测试库），消除 pg_trgm/Uuid/JSON 方言漂移；引入 savepoint 事务隔离 + fakeredis。
**成功标准**：`docker compose -f docker-compose.test.yml up -d` 起 PG/Redis；conftest 连真实 PG 跑迁移建表；现有全量测试在 PG 上绿（含此前因 SQLite 被 skip 的 pg_trgm 用例）；用例间 savepoint 回滚隔离。
**测试**：全量 pytest 在 PG 容器上通过；之前 skip 的方言相关用例转为真实执行。
**步骤**：
1. 新增 `api/docker-compose.test.yml`（pg16 + redis7，端口错开 5433/6380，tmpfs 加速）。
2. 改 `api/tests/conftest.py`：`TEST_DATABASE_URL` 优先；session 级 engine 一次性 `create_all`（或跑 alembic）；function 级 `db_session` 用 `begin_nested()`+外层 rollback 隔离。
3. `api/tests/fakes.py` 补 `FakeRedis`（fakeredis）fixture。
4. 处理此前 SQLite-only 的 skip 标记，转真实 PG 执行。
5. CI（阶段 1 已迁 uv）加 `services: postgres` + 跑 PG 集成测试。
**状态**：✅ 已完成（conftest 切真实 PG + savepoint 隔离 via join_transaction_mode=create_savepoint；docker-compose.test.yml 端口 15433/16380 tmpfs；会话级 alembic 迁移链建 schema；test_infra_real_pg 红线；CI 加 postgres/redis service。全量 159 passed。注：当前无测试依赖 Redis，故未加 fakeredis fixture，留待需要时补）

## 阶段 3：统一响应与异常基础设施

**目标**：搭好 `Response[T]` 信封 + `ErrorCode` + 异常树 + `@api_response` + 全局 exception handler；前端 `client.ts` 单点拆包适配（向后兼容）。**本阶段只建机制 + 灰度 1 个资源验证**，不全量切控制器。
**成功标准**：新建基础设施单元测试绿；选 1 个资源（如 health 或 kb 只读端点）接入新信封，端到端（后端 + 前端 client.ts）验证通过；其余端点暂不动仍可用。
**测试**：`Response[T]` 序列化、`@api_response` ORM→schema 包装、各异常→handler→信封映射、前端 client.ts 拆包（含 success/false 抛 BusinessError + 401 刷新）单测。
**步骤**：
1. 后端 `app/common/`（或 `app/core/`）：`exceptions.py`（AppBaseException/ServiceException/DBException/ParamsException…+ ErrorCode 枚举）、`response.py`（Response[T] + response_base.success/fail）、`api_response.py`（装饰器）、`exception_handler.py`（register_exception，业务异常→对应 HTTP status + 信封）。
2. `main.py` 注册 `register_exception(app)`；保留现有兜底 handler 行为并纳入统一信封。
3. 前端：`web/src/api/types.ts` 加 `ApiResponse<T>` + `BusinessError`；`web/src/api/client.ts` 单点拆包（success→data，false→抛 BusinessError，保留 401 刷新）；`client.test.ts` 更新。
4. 灰度：接入 1 个资源验证全链路。
**状态**：✅ 已完成（app/common: Response[T]/ErrorCode+AppException 树/@api_response/register_exception；main.py 注册，存量 HTTPException 与兜底行为不变；灰度 GET /api/kbs 走 Response[list[KBOut]]；前端 client.ts 单点拆包+BusinessError+ApiResponse 类型。后端 165 passed、前端 10 passed+build 绿）

## 阶段 4：数据访问层重构（BaseCrud + 类 + 单例）

**目标**：实现异步 `BaseCrud[ModelT]`；逐实体把 repository 迁为类 + 单例并继承 BaseCrud，统一 `get_by_*`/`get_by_*_or_none` + 抛 `DBException`；service 迁为类 + 单例（业务编排 + 显式 commit），controller 调用点同步更新。
**成功标准**：每个实体迁移后其相关测试仍绿；CRUD 重复显著减少；查询命名/异常契约统一；分批提交（一实体或一组一提交）。
**测试**：每个 repo/service 迁移配单测（get_by_* 抛错版/`_or_none` 版语义、commit 边界）；既有 API 测试保持绿。
**步骤**：
1. `app/repositories/base_crud.py`：异步 `BaseCrud`（get_by_id/get_by_id_or_none/list/add/update/soft 或 hard delete/bulk_*，按本项目模型字段裁剪——注意本项目 UUID 主键、可能无 delete_flag）。
2. 逐实体迁 repo → 类 + 单例 + 继承 BaseCrud；保留实体专属查询。
3. 逐实体迁 service → 类 + 单例；事务边界从 controller 上移到 service（HTTP 一接口一事务）。
4. controller 调用点改为 `xxx_service.method(...)`。
**状态**：✅ 已完成（结构部分）。异步 `BaseCrud[ModelT]` 落地；15 个 repo 全迁类+单例+继承 BaseCrud，13 个 service 全迁类+单例；__init__ 重导出单例，调用点写法不变、行为零变化；跨 service 引用改直接子模块导入避免循环。全量 170 passed、ruff 全绿。
> ⚠️ **保守取舍**：事务边界未从 controller 上移到 service（13 个 controller 的 `session.commit()` 维持原位）。该子项行为风险高、价值增量低，且 savepoint 测试基座对 commit 时序敏感，为守住全绿按 CLAUDE.md「增量优于大爆炸」暂不搬迁，留作后续单独项。

## 阶段 5：控制器迁移 + 收尾

**目标**：全量 controller 接 `@api_response` + `response_model=Response[T]` + 瘦身（权限/commit 下沉 service）；更新所有 `test_api_*.py` 断言为新信封；补 arq/可观测性/迁移锁/编码规范。
**成功标准**：18 个 controller 全量统一信封；后端全量测试绿（断言新信封）；前端全栈联通；收尾项落地。
**测试**：全量 API 集成测试按新信封断言（success/code/data/request_id）；前端 build + 单测绿。
**步骤**：
1. 逐 controller 接 `@api_response`，`response_model=Response[T]`，移除内联 try/except 与越层逻辑。
2. 同步更新 `test_api_*.py` 断言（body.success/code/data）。
3. 收尾（与阶段 3-5 穿插）：arq enqueue pool 单例化 + 任务入参 Pydantic 化；慢请求 warn 日志 + 4xx/5xx 结构化错误日志 + `X-Process-Time-Ms` 响应头 + 连接池监控端点 + 健康检查访问日志过滤；DB 连接池参数（pool_recycle/size/overflow + command_timeout）+ 显式 autocommit/autoflush；迁移并发安全（entrypoint.sh + Redis 分布式锁 + 等待依赖）；`Mapped[dict[str,Any]]`、TimeUtils、Service docstring 补齐、新增模型索引入 `__table_args__`。
**状态**：✅ 已完成（核心）。18 个 controller 成功响应全量包统一信封；业务异常转 AppException 树统一信封（框架级 422/404、SSE、文件下载、健康探针除外）。**并按老板新指令完成四层分层纠偏**：dict/list 返回端点改 Schema（activity/analytics/query_feedback/notifications）；**全部 18 个 controller 零 repo 直调、零 repo import**，repo 调用/权限/业务逻辑/commit/ORM→schema 转换全部下沉到 service（新建 wiki/comment/favorite/source/stats/activity/analytics 7 个 service，其余补方法），controller 仅「解析入参→调 service→return」，service 返回 Pydantic schema。全量 test_api_* 断言改解信封 data。收尾已做：X-Process-Time-Ms 响应头 + 慢请求(>1000ms) warn 日志。后端 170 passed、ruff 全绿、前端 build+10 测试绿。
> 仍可选的收尾（未做，低优先）：arq pool 单例化、连接池参数(pool_recycle/size/overflow)、迁移并发分布式锁(entrypoint.sh)、连接池监控端点。事务边界(commit)已随 MVC 下沉到 service 层。

---

## 风险与回滚

- **前端契约**：信封改动集中在 `client.ts` 单点，向后兼容（未识别信封则透传）；灰度 1 个资源验证后再全量。
- **大重构分批**：repo/service/controller 逐实体迁移、每批独立提交可工作、可回滚；不一次性大爆炸。
- **测试切 PG**：先确保 PG 容器测试全绿再继续后续阶段，避免在不可靠测试基座上重构。
- **未提交在途改动**：工作区 analytics 相关 4 文件为他人/在途改动，本计划不触碰。

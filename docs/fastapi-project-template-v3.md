# FastAPI 后端项目模板

> 本文档把当前服务的工程规范、目录结构、关键基础设施代码、运行方式、部署形态等抽离成一份**可直接落地**的项目模板。新项目按本文档实现，能继承同样的分层、命名、异常、响应、并发、可观测性、定时任务、部署形态。
>
> 适用范围：**Python 3.12+ / FastAPI / SQLAlchemy 2.x（同步）/ MySQL 8.0 / Redis / funboost** 的后端服务，尤其是需要 Web API + 异步 Worker + 定时调度三类进程并存、可多 Pod 部署的中型服务。
>
> **v3 增量**（相对 v2）：
> - §3.4 新增：`scripts/start_feishu_ws.py` 飞书 WebSocket Leader 进程入口（业务长连接 + Leader 选举模板）
> - §6.4 新增："`Mapped[X]` 与 `mapped_column()` 类型契约"小节，明确两条强制规则（X 必须是 Python 类型；`nullable` 与可空性双写一致）
> - §6.7 内补充："单条查询：默认抛错，按需 `_or_none`" 子小节；查询规范从"`is_raise_exception` 参数模式" → 改为"`get_xxx` / `get_xxx_or_none` 双方法模式"；BaseCrud / Country 全栈示例同步更新
> - §7.5 新增：业务核心域 `src/core/`（`analyzers/` `llm/` `matchers/` `prompts/` `renderers/` `senders/`），service 只做编排，领域逻辑下沉
> - §18.5 新增：`src/common/context.py` 请求上下文（trace_id / 用户身份等贯穿）
> - §18.6 新增：`src/common/dataclasses.py` 跨层数据传递结构
> - §18.7 新增：`src/common/enums.py` 全局 Enum 集中
> - §18.8 新增：`src/common/pagination.py` + `schemas/pagination.py` 统一分页入参 / 出参
> - §18.9 新增：`src/common/schema.py` 通用 schema 基类
> - §19.8 新增：`src/utils/json.py` 统一 JSON 序列化（支持 datetime / Enum / Pydantic / dataclass）
> - §19.9 新增：`src/utils/debug_logger.py` 开发期诊断日志
> - §19.10 新增：`src/utils/trace.py` Phoenix span 装饰器（业务级追踪）
> - §19.11–19.12 占位：项目特化 utils（`feishu/` / `gateway_client.py`）说明位置
> - §11.x / §13.x / 全文：所有 service / crud 参数从 `db: Session` 统一改为 `session: Session`
> - 各处规范文字润色，配套更新 §16 速查表与 §17 落地检查表
>
> **v2 增量**（相对 v1）：
> - §1.1 / §6.1.1 增加 MySQL 驱动选择对比（`mysqlclient` 生产推荐 / `PyMySQL` 开发友好）
> - §6.2 增加 `connect_timeout` / `read_timeout` / `write_timeout` 超时控制
> - §6.2.2 新增：`@event.listens_for(engine, "connect")` 强制会话级 `sql_mode='STRICT_TRANS_TABLES'`
> - §22 新增：自动化测试章节（`tests/unit/` + `tests/integration/` + savepoint 隔离 fixture + docker-compose 测试环境）
> - §23 新增：MySQL 8.0 生产环境七大坑（gone away / 死锁重试 / 跳号 / 索引长度 / 大偏移分页 / 连接池公式 / 线程池）
> - §24 新增：性能与可观测性（慢查询、EXPLAIN、连接池监控、应用层中间件计时）

---

## 0. 模板能给你什么

- 一套已经跑通的**多进程拆分**：`web` / `worker` / `scheduler` 三个独立进程入口，由 supervisor 统一守护
- 严格的**四层分层**：Controller → Service → CRUD → Model，每层职责边界清晰，禁止越层
- 一个 **`BaseCrud[ModelT]` 父类**，覆盖 95% 的标准 CRUD，子类只写实体专属方法
- 一套**统一响应 + 统一异常**：`Response[T]` + `@api_response()` + 全局 exception handler，业务代码只 raise 业务异常，HTTP 形态由框架统一渲染
- **环境感知配置**：基于 `pydantic-settings` 的多继承聚合配置，支持 `.env` / 环境变量 / Apollo 远程配置
- **多 Pod 安全**的 Redis 工具：自动 key 前缀代理 + 分布式锁 + funboost `ApsJobAdder` 调度
- **Docker + supervisor** 单镜像四进程部署形态，开箱即用

---

## 1. 技术栈

| 类别 | 选型 | 备注 |
|------|------|------|
| Python | 3.12+ | 全面使用 PEP 695 / 内建泛型语法 |
| 包管理 | uv | `uv sync --frozen` / `uv run xxx` |
| Web 框架 | FastAPI ≥ 0.128 | `lifespan` + 应用工厂 |
| ASGI Server | uvicorn ≥ 0.39 | 强制单 worker（见配置规则） |
| ORM | SQLAlchemy 2.x | **统一同步**，禁止 async session |
| 数据库 | MySQL 8.0 | 驱动二选一：`mysqlclient`（生产推荐，C 扩展性能好）/ `pymysql`（纯 Python，跨平台无痛） |
| 迁移 | Alembic ≥ 1.18 | `src/db/alembic.ini` 集中管理 |
| 缓存/队列 | Redis 7 | `redis-py`，支持 standalone / Sentinel / Cluster |
| 异步任务 | funboost 54.x | Redis Stream broker；`ApsJobAdder` 做调度 |
| 配置 | pydantic-settings ≥ 2.12 | 多继承聚合 |
| 序列化 | msgspec | 替代 stdlib JSON 提速 |
| 链路追踪 | asgi-correlation-id + Phoenix（可选） | `X-Request-ID` 贯穿 |
| 日志 | nb_log | 多文件路由 + uvicorn access 过滤 |
| 代码质量 | ruff + mypy | line-length=120，target=py312 |

完整 `pyproject.toml` 模板见 §1.1。

### 1.1 `pyproject.toml` 完整模板

完整模板按"项目元信息 → 依赖（按职责分组）→ 可选依赖 → 工具配置（pytest / mypy / ruff）"组织。直接复制后改 `name` / `description` / 依据所选模块裁剪依赖即可。

```toml
# ==============================================================================
# 项目元信息
# ==============================================================================
[project]
name = "<your-service-name>"                 # PyPI 风格小写连字符；与目录名解耦即可
version = "0.1.0"                            # 推荐 SemVer；CI 构建可由 git tag / commit 注入覆盖
description = "<一句话描述本服务，会显示在生成的 wheel 元信息里>"
readme = "README.md"
requires-python = ">=3.12"                   # 全项目按 3.12 写代码（PEP 695 / 内建泛型语法）
license = { text = "Proprietary" }           # 开源项目改为 "MIT" / "Apache-2.0" / { file = "LICENSE" }
authors = [
    { name = "<Your Team>", email = "<team@example.com>" },
]
keywords = ["fastapi", "sqlalchemy", "funboost"]
classifiers = [
    "Programming Language :: Python :: 3.12",
    "Framework :: FastAPI",
    "Operating System :: POSIX :: Linux",
]

# ------------------------------------------------------------------------------
# 运行时依赖：按"职责"分组注释，便于裁剪 / 升级时定位影响范围
# ------------------------------------------------------------------------------
dependencies = [
    # ── Web / API ─────────────────────────────────────────────────────────────
    "fastapi>=0.128.0",                      # Web 框架
    "uvicorn>=0.39.0",                       # ASGI server（强制单 worker，见 §3）
    "asgi-correlation-id>=4.3.4",            # X-Request-ID 中间件
    "starlette-context>=0.4.0",              # 请求上下文（trace_id 等）
    "jinja2>=3.1.0",                         # FastAPI HTML 响应 / 模板渲染（无需可删）

    # ── 数据校验 / 配置 ───────────────────────────────────────────────────────
    "pydantic>=2.12.0",                      # 数据校验
    "pydantic-settings>=2.12.0",             # 多继承聚合配置（见 §5）

    # ── 数据库 ───────────────────────────────────────────────────────────────
    "sqlalchemy>=2.0.46",                    # ORM（统一同步使用，见 §6）
    # 驱动二选一（详见 §6.2 对比表）：
    #   生产推荐 mysqlclient（C 扩展，性能最好；需系统 libmysqlclient-dev）
    #   开发推荐 pymysql      （纯 Python，跨平台无痛；性能差 30-50%）
    "pymysql>=1.1.2",                        # MySQL 驱动（同步）；切 mysqlclient 时改为 "mysqlclient>=2.2"
    "cryptography>=42.0",                    # PyMySQL + caching_sha2_password 必需；用 mysqlclient 可删
    "alembic>=1.18.3",                       # 迁移工具

    # ── 缓存 / 队列 / 调度 ────────────────────────────────────────────────────
    "redis>=7.1.0",                          # Redis 客户端（含 Sentinel / Cluster / SSL）
    "funboost==54.8",                        # 异步任务框架（**锁定版本，避免 broker 协议变动**）
    "apscheduler>=3.11.0",                   # funboost ApsJobAdder 底层依赖

    # ── HTTP 客户端 ───────────────────────────────────────────────────────────
    "httpx>=0.25.0",                         # 同步/异步 HTTP 客户端

    # ── 序列化 / 工具 ─────────────────────────────────────────────────────────
    "msgspec>=0.20.0",                       # 高性能 JSON（替代 stdlib，FastAPI 响应用）
    "pyyaml>=6.0.2",                         # example-env.yaml / 配置解析
    "pytz>=2024.1",                          # 时区辅助（虽默认用 zoneinfo，第三方库偶尔需要）
    "pycryptodome>=3.23.0",                  # 配置 ENC(xxx) 解密（按需）

    # ── 日志 ─────────────────────────────────────────────────────────────────
    "nb-log==14.2",                          # 多文件路由 + 彩色 + 滚动（**锁定版本**）

    # ── 可观测性（可选；不需要 Phoenix 追踪时整组删除）────────────────────────
    "arize-phoenix-otel>=0.6.1",             # Phoenix LLM 追踪
    "openinference-instrumentation-openai>=0.1.0",
    "openinference-semantic-conventions>=0.1.0",

    # ── 第三方业务 SDK（按需保留 / 删除）──────────────────────────────────────
    "lark-oapi>=1.4.0",                      # 飞书 OpenAPI（不接飞书可删）
    "openai>=1.0.0",                         # OpenAI / 兼容协议 LLM（不调 LLM 可删）
]

# ------------------------------------------------------------------------------
# 可选依赖：用 uv sync --extra dev / --extra test 按需安装
# ------------------------------------------------------------------------------
[project.optional-dependencies]
dev = [
    "ruff>=0.6.0",                           # 代码风格 + lint
    "mypy>=1.10.0",                          # 类型检查
    "ipython>=8.0.0",                        # 调试 REPL
    "ipdb>=0.13.0",                          # 调试断点
]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.10.0",
    "httpx>=0.25.0",                         # FastAPI TestClient 依赖
    "fakeredis>=2.20.0",                     # Redis fake，单元测试不依赖真实 Redis（见 §22.4）
]

# ==============================================================================
# uv 配置（uv ≥ 0.4）
# ==============================================================================
[tool.uv]
# 默认安装 dev 依赖；CI 跑生产构建时用 `uv sync --frozen --no-dev`
dev-dependencies = ["ruff>=0.6.0", "mypy>=1.10.0"]
# 严格按 lock 解析，禁止偷偷升级
resolution = "highest"
# 国内镜像源示例（按需开启）
# index-url = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 如果引用本地 / git 包，写在这里（示例：本地编辑安装）
# [tool.uv.sources]
# my-shared-lib = { path = "../shared-lib", editable = true }
# funboost = { git = "https://github.com/ydf0509/funboost", rev = "v54.8" }

# ==============================================================================
# pytest
# ==============================================================================
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"                        # 自动识别 async test，无需逐个 @pytest.mark.asyncio
addopts = [
    "-v",                                    # 详细输出
    "--strict-markers",                      # 未注册 marker 直接报错，避免拼写错误
    "--tb=short",                            # 简短 traceback
    # "--cov=src",                           # 需要覆盖率时打开
    # "--cov-report=term-missing",
    # "--cov-fail-under=70",
]
markers = [
    "integration: 需要真实 DB / Redis 的集成测试",
    "slow: 慢测试（默认跳过，CI nightly 跑）",
]
filterwarnings = [
    "ignore::DeprecationWarning:pkg_resources.*",
    "ignore::DeprecationWarning:pydantic.*",
]

# ==============================================================================
# mypy
# ==============================================================================
[tool.mypy]
python_version = "3.12"
warn_return_any = false                      # SQLAlchemy 大量 Any 返回，关掉避免噪音
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_untyped_defs = false                # 起步阶段宽松；存量项目稳定后再调 true
disallow_incomplete_defs = false
check_untyped_defs = true                    # 即使没注解也做检查
no_implicit_optional = false                 # 兼容旧风格 `def f(x: str = None)`
ignore_missing_imports = true                # 第三方无 stub 时不报错

# 针对特定模块放宽 / 收紧
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
check_untyped_defs = false

[[tool.mypy.overrides]]
module = ["funboost.*", "nb_log.*", "lark_oapi.*"]
ignore_errors = true                         # 第三方库自身类型问题，整体忽略

# ==============================================================================
# ruff
# ==============================================================================
[tool.ruff]
line-length = 120
target-version = "py312"
extend-exclude = [
    ".venv",
    "build",
    "dist",
    "src/db/migrations/versions",            # alembic 自动生成的迁移文件
]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes（未使用导入 / 变量）
    "I",   # isort（导入排序）
    "C",   # flake8-comprehensions（推导式优化）
    "B",   # flake8-bugbear（常见 bug 模式）
    # 想更严格可继续打开（按存量逐步引入）：
    # "UP",  # pyupgrade（强制现代语法）
    # "SIM", # flake8-simplify
    # "RUF", # ruff 自身规则
]
ignore = [
    "E501",  # line too long（line-length=120 已覆盖；超长字符串自然换行不强制）
    "B008",  # 函数默认值里调用函数（FastAPI Depends() 必须如此）
    "C901",  # 函数过长 / 过复杂（业务流程自然偏长）
    "B006",  # 可变默认值（按规则审查，不一刀切）
    "B904",  # raise ... from err（项目允许丢上下文，避免噪音）
    "E741",  # 变量名与关键字相似（`l` 在循环中常见）
    "E722",  # 裸 except（worker 兜底场景需要）
    "B027",  # 抽象类空方法
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]                     # __init__.py 允许未使用的 import（re-export）
"tests/**/*.py" = ["S101", "D"]              # 测试允许 assert / 无 docstring
"src/db/migrations/**/*.py" = ["E402", "F401", "I001"]

[tool.ruff.lint.isort]
known-first-party = ["src"]                  # 让本项目代码独立成 isort 区块
combine-as-imports = true
force-sort-within-sections = false
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", "fastapi.Path", "fastapi.Body", "fastapi.Header"]

[tool.ruff.format]
quote-style = "double"                       # 字符串统一双引号
indent-style = "space"
skip-magic-trailing-comma = false            # 末尾逗号触发多行展开（与 isort 风格一致）
line-ending = "auto"
docstring-code-format = true                 # 格式化 docstring 内的代码块
```

### 1.2 依赖 / 配置变更工作流

| 操作 | 命令 | 说明 |
|------|------|------|
| 安装全部依赖（含 dev） | `uv sync` | 本地开发用 |
| 严格按 lock 安装 | `uv sync --frozen` | CI / Docker 用，禁止偷偷升级 |
| 生产镜像（不装 dev） | `uv sync --frozen --no-dev` | Dockerfile 推荐写法 |
| 添加运行时依赖 | `uv add <package>` | 自动写入 `[project].dependencies` 并更新 lock |
| 添加 dev 依赖 | `uv add --dev <package>` | 写入 `[project.optional-dependencies].dev` |
| 升级单包 | `uv lock --upgrade-package <pkg>` | 只升一个，避免大面积变更 |
| 升级全部 | `uv lock --upgrade` | 谨慎使用，必须跑完整测试 |
| 锁定版本（避免大版本漂移） | `"funboost==54.8"` 或 `"nb-log==14.2"` | broker 协议 / 私有 API 不稳定的库用 `==` |

**版本约束规范**：

- **核心框架 / 业务关键路径**：用 `>=` + 已验证版本下限（如 `fastapi>=0.128.0`）
- **协议易变 / 内部 API 不稳定**：用 `==`（如 `funboost==54.8`、`nb-log==14.2`）
- **新增依赖必须**：执行 `uv add` 让 `uv.lock` 自动同步；禁止只手动改 `pyproject.toml` 不更新 lock

### 1.3 镜像 / 私有源（按需）

国内或企业私有源场景在 `[tool.uv]` 增加：

```toml
[tool.uv]
index-url = "https://pypi.tuna.tsinghua.edu.cn/simple"

[[tool.uv.index]]
name = "company-internal"
url = "https://pypi.internal.company.com/simple"
default = false                              # 仅当公开 PyPI 找不到时才查
```

或在 CI / Docker 里通过环境变量注入，避免把企业内网地址提交到代码仓库：

```bash
export UV_INDEX_URL="https://pypi.internal.company.com/simple"
uv sync --frozen
```

---

## 2. 目录结构

```
<project-root>/
├── backend/                           # 项目根
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .python-version                # 3.12
│   ├── funboost_config.py             # funboost broker 连接（必须放根目录）
│   ├── nb_log_config.py               # nb_log 全局配置
│   ├── example-env.yaml               # 环境变量示例（敏感字段 ENC(xxx)）
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   ├── sources.list
│   │   └── supervisor.conf            # web / worker / scheduler 三进程定义
│   ├── scripts/                       # 仅放服务启动 + DB 建库/迁移脚本
│   │   ├── start_web.py
│   │   ├── start_worker.py
│   │   ├── start_scheduler.py
│   │   ├── start_feishu_ws.py         # 飞书 WS 长连接 leader 进程（可选）
│   │   ├── init_db.py                # 建库脚本（数据库不存在时跑连通性 ping + CREATE DATABASE）
│   │   └── upgrade_db.py             # Alembic 迁移应用（含 Redis 分布式锁，多 Pod 安全）
│   └── src/
│       ├── app.py                     # FastAPI 应用工厂（唯一允许 src 内的入口文件）
│       ├── configs/
│       │   ├── app_configs.py         # 多继承聚合配置
│       │   └── __init__.py            # 暴露 configs = Configs() 单例
│       ├── common/
│       │   ├── constants.py           # 路径常量、跨模块业务常量
│       │   ├── redis_keys.py          # 所有 Redis key 集中常量类
│       │   ├── context.py             # starlette_context 类型化协议
│       │   ├── dataclasses.py         # 通用 dataclass（如 SnowflakeInfo）
│       │   ├── enums.py               # 枚举基类（带 get_member_keys 等通用方法）
│       │   ├── pagination.py          # fastapi-pagination 集成
│       │   ├── schema.py              # 通用 Pydantic 类型（CustomPhoneNumber / CustomEmailStr）
│       │   ├── schemas/               # 分页 Pydantic schema
│       │   │   └── pagination.py
│       │   ├── api_response.py        # @api_response 装饰器
│       │   ├── response/
│       │   │   ├── response_schema.py # Response[T] + ResponseBase
│       │   │   └── response_code.py
│       │   └── exception/
│       │       ├── errors.py          # ErrorCode + 自定义异常树
│       │       └── exception_handler.py
│       ├── controllers/
│       │   ├── router.py              # app_router = system + api/v1
│       │   ├── api/v1/
│       │   │   ├── router.py          # v1 子路由聚合
│       │   │   └── <entity>.py        # 一资源一文件
│       │   └── system/
│       │       ├── router.py
│       │       └── health.py
│       ├── core/                      # 业务核心域（领域逻辑剥离，可选层；详见 §7.6）
│       │   ├── analyzers/             # 领域分析器（会议质量 / GM 能力等）
│       │   ├── llm/                   # LLM 客户端封装
│       │   ├── matchers/              # 模板 / 主题匹配器
│       │   ├── prompts/               # Prompt 模板构造器
│       │   ├── renderers/             # 飞书卡片 / 报告渲染器
│       │   └── senders/               # 飞书消息发送适配器
│       ├── services/                  # 一实体一文件 + 类 + 单例
│       │   └── <entity>_service.py
│       ├── cruds/
│       │   ├── base_crud.py           # BaseCrud[ModelT] 父类
│       │   └── <entity>_crud.py
│       ├── models/
│       │   ├── base.py                # Base + 公共字段
│       │   ├── enums.py               # 全部 Enum 集中
│       │   ├── __init__.py            # 显式导入 + __all__ 维护
│       │   └── <entity>.py
│       ├── schemas/                   # Pydantic 入参 / 出参 schema
│       │   └── <module>.py
│       ├── db/
│       │   ├── alembic.ini            # Alembic 配置（在此目录执行）
│       │   ├── engines.py             # sync_engine + SessionLocal 单例
│       │   ├── session.py             # get_db (FastAPI) / get_db_session (worker)
│       │   ├── migrate.py             # 升级逻辑入口
│       │   └── migrations/
│       │       └── versions/
│       ├── middleware/
│       │   ├── request_logging_middleware.py
│       │   └── error_logging_middleware.py
│       ├── worker/                    # funboost 业务 consumer
│       │   └── <name>_worker.py
│       ├── schedulers/                # funboost ApsJobAdder 触发的扫描器
│       │   └── <name>_scanner.py
│       └── utils/
│           ├── log.py                 # init_logger / get_logger
│           ├── redis.py               # redis_client 包装器 + 锁
│           ├── time.py                # TimeUtils（强制北京时间）
│           ├── uuid.py
│           ├── trace_id.py
│           ├── observe.py             # Phoenix init
│           ├── json.py                # 自定义 JSON 编解码（datetime / Enum / Decimal）
│           ├── serializers.py         # MsgSpecJSONResponse FastAPI 响应类
│           ├── debug_logger.py        # 调试专用 logger（按需开关，不进生产日志）
│           ├── trace.py               # @trace 装饰器（业务函数级 span，配合 Phoenix）
│           ├── gateway_client.py      # 内部网关 HTTP 调用客户端封装（项目特化）
│           └── feishu/                # 飞书 SDK 封装（项目特化）
│               ├── event.py
│               ├── sdk.py
│               └── ws_client.py
└── tests/
    ├── conftest.py                # 全局 fixture（test_engine / db_session / client）
    ├── unit/                      # 单元测试：业务规则验证
    │   └── test_<service>.py
    ├── integration/               # 集成测试：真实 MySQL + 完整 HTTP 链路
    │   ├── conftest.py
    │   └── test_<entity>_api.py
    └── scripts/                   # 数据初始化、诊断、修数等手工脚本
        └── init_data/
```

**关键约束**：
- `src/` 里**唯一**允许的启动文件是 `src/app.py`（FastAPI 应用工厂）；其它入口都在 `scripts/`。
- `scripts/` **只放**服务启动脚本（`start_*.py`）和建库/迁移脚本（`init_db.py` / `upgrade_db.py`）。
- `tests/scripts/`：数据初始化、诊断、修数等**手工脚本**（按 `tests/scripts/init_data/` 与根目录区分），不进 pytest 自动收集。
- `tests/unit/` + `tests/integration/`：自动化测试用例（见 §22）。

---

## 3. 多进程模型与启动入口

服务由 4 类进程组成，每类一个独立入口，supervisor 统一守护：

| 进程 | 入口脚本 | 作用 |
|------|----------|------|
| `web` | `scripts/start_web.py` | FastAPI HTTP 服务 |
| `worker` | `scripts/start_worker.py` | funboost 业务 consumer |
| `scheduler` | `scripts/start_scheduler.py` | funboost `ApsJobAdder` 注册 + scanner consumer |
| `feishu_ws`（业务长连接，可选） | `scripts/start_feishu_ws.py` | 飞书 WebSocket Leader 进程：消费飞书事件 WS，push 至 funboost 队列；多 Pod 时 Redis 锁选主，单 Pod 持锁运行（详见 §3.4） |

**为什么必须拆开？**
- web 单 worker（强约束，见配置）— 多 worker 会让进程级单例（追踪器、调度器）状态紊乱
- worker / scheduler 是无状态消费者 — 通过 funboost 队列与 web 解耦，可独立扩缩容
- scheduler 与 worker 拆分 — `ApsJobAdder` 内置 Redis 分布式锁保证多 Pod 只有一个实例触发 schedule，触发后由 worker 真正执行

### 3.1 `scripts/start_web.py` 模板

```python
"""uvicorn [start_web] 进程入口 (FastAPI)"""

from src.utils.log import init_logger  # 必须最前面

init_logger("main", "run_main.log")

import os

import uvicorn

from src.configs import configs
from src.utils.observe import init_phoenix


def main() -> None:
    if configs.UVICORN_WORKER_NUM != 1:
        raise RuntimeError("UVICORN_WORKER_NUM must be 1（追踪器/调度器是进程级单例，多 worker 会冲突）")

    init_phoenix(service_name="web")

    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run("src.app:app", host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
```

### 3.2 `scripts/start_worker.py` 模板

```python
"""业务 Consumer 进程入口（[worker] 进程）"""

from src.utils.log import init_logger  # 必须最前面

init_logger("worker", "run_worker.log")

from funboost import ctrl_c_recv

from src.utils.log import get_logger
from src.utils.redis import init_redis
from src.worker.<your_worker> import <your_task>

logger = get_logger("worker")


def main() -> None:
    init_redis()
    logger.info("[Worker] 启动业务 consumer ...")
    <your_task>.consume()
    ctrl_c_recv()


if __name__ == "__main__":
    main()
```

### 3.3 `scripts/start_scheduler.py` 模板

```python
"""scheduler 进程入口"""

from src.utils.log import init_logger
init_logger("scheduler", "run_scheduler.log")

from funboost import ApsJobAdder, ctrl_c_recv

from src.configs import configs
from src.schedulers.<scanner> import <scanner_task>
from src.utils.redis import init_redis


def register_schedules() -> None:
    ApsJobAdder(<scanner_task>, job_store_kind="redis").add_push_job(
        trigger="interval",
        seconds=configs.<INTERVAL_FIELD>,
        kwargs={"task": {}},
        id="<scanner_id>",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def main() -> None:
    init_redis()
    register_schedules()
    <scanner_task>.consume()
    ctrl_c_recv()


if __name__ == "__main__":
    main()
```

### 3.4 `scripts/start_feishu_ws.py` —— 飞书 WebSocket Leader 进程

属于"业务专用长连接"类进程。**仅当本服务需要消费飞书事件 WS 时才存在**；通用 FastAPI 服务可省略。

- **形态**：基于 Redis 分布式锁的 leader 选举进程；多 Pod 部署时**仅有一个 Pod** 持锁成为 leader 并维持 WS 长连接，非 leader 持续抢锁待命
- **职责**：消费飞书事件 WS，把事件 push 到 funboost 队列（如 `QUEUE_RAW_EVENTS`），由 worker 进程 consume
- **故障转移**：leader 进程崩溃时锁过期，下一个 Pod 自动接管
- **为什么单独开一类进程**：WS 不属于 web/worker/scheduler 任意一类（不响应 HTTP、不消费队列、不调度任务），需要独立进程维持长连接

具体代码参考项目实现（`scripts/start_feishu_ws.py`），本模板不展示业务特化代码。

**执行方式**：
- 生产：supervisor 拉起（见 §12）。
- 本地服务：`uv run scripts/start_<web|worker|scheduler>.py`。
- 本地辅助脚本：`uv run python -m scripts.<name>`（用模块语法，避免 PYTHONPATH 问题）。

---

## 4. FastAPI 应用工厂

`src/app.py` 是 **`src/` 下唯一允许的入口文件**。中间件按"洋葱模型"从内到外注册，CorrelationId 必须最外层以确保所有响应都带 `X-Request-ID`。

```python
"""FastAPI 应用工厂"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.common.exception.exception_handler import register_exception
from src.configs import configs
from src.controllers.router import app_router
from src.middleware.error_logging_middleware import ErrorLoggingMiddleware
from src.middleware.request_logging_middleware import RequestLoggingMiddleware
from src.utils.log import get_logger
from src.utils.redis import init_redis

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_redis()
    logger.info("[Lifespan] Redis 已初始化")
    yield
    logger.info("[Lifespan] 应用关闭")


def create_app() -> FastAPI:
    if "prod" in configs.ENVIRONMENT:
        app = FastAPI(title="<service-name>", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    else:
        app = FastAPI(title="<service-name>", root_path=configs.FASTAPI_ROOT_PATH, docs_url="/docs", lifespan=lifespan)

    register_exception(app)

    # 中间件顺序：从内到外
    app.add_middleware(ErrorLoggingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    if configs.ENABLE_CORS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=configs.CORS_ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=configs.CORS_EXPOSE_HEADERS,
        )

    # CorrelationId 必须最外层
    app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID", update_request_header=True)

    app.include_router(app_router)
    return app


app = create_app()
```

---

## 5. 配置体系（pydantic-settings 多继承）

配置按**功能域拆类**，`Configs` 通过多继承聚合所有子类，业务代码只通过 `configs.FIELD_NAME` 访问，禁止直接 import 子类。

### 5.1 `src/configs/app_configs.py`

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.common.constants import ENV_PATH


class ServiceConfig(BaseSettings):
    ENVIRONMENT: str = Field(default="dev", description="dev/uat/prod")
    LOG_LEVEL: str = Field(default="DEBUG")
    UVICORN_WORKER_NUM: int = Field(default=1, description="**必须为 1**")


class CORSConfig(BaseSettings):
    ENABLE_CORS: bool = Field(default=True)
    CORS_ALLOWED_ORIGINS: list[str] = Field(default=["*"])
    CORS_EXPOSE_HEADERS: list[str] = Field(default=["X-Request-ID"])


class MySQLConfig(BaseSettings):
    MYSQL_USER: str = Field(default="")
    MYSQL_PASSWORD: str = Field(default="")
    MYSQL_HOST: str = Field(default="127.0.0.1")
    MYSQL_PORT: int = Field(default=3306)
    MYSQL_DB: str = Field(default="<your_db>")
    MYSQL_DRIVER: str = Field(default="pymysql", description="pymysql / mysqldb（mysqlclient）")
    POOL_SIZE: int = Field(default=50)
    POOL_MAX_OVERFLOW: int = Field(default=50)

    # 连接超时：防止网络异常时请求线程被永久 hang 住
    DB_CONNECT_TIMEOUT: int = Field(default=10, description="建连超时秒")
    DB_READ_TIMEOUT: int = Field(default=30, description="读超时秒")
    DB_WRITE_TIMEOUT: int = Field(default=30, description="写超时秒")

    @property
    def db_uri(self) -> str:
        from urllib.parse import quote_plus
        # mysql+pymysql://...  或  mysql+mysqldb://...
        return (
            f"mysql+{self.MYSQL_DRIVER}://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )


class RedisConfig(BaseSettings):
    REDIS_HOST: str = Field(default="127.0.0.1")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_KEY_PREFIX: str | None = Field(default="<your_app>_dev",
        description="按环境区分：dev/uat/prod 用不同前缀，避免共享 Redis 时互相污染")


class WorkerConfig(BaseSettings):
    MAX_RETRIES: int = Field(default=3)
    # 各个 worker 的 QPS 配置驱动，禁止硬编码
    <YOUR_WORKER>_QPS: int = Field(default=10)


class Configs(
    ServiceConfig,
    CORSConfig,
    MySQLConfig,
    RedisConfig,
    WorkerConfig,
    # ... 其余子配置
):
    """应用配置：多继承聚合，优先级 init > env > .env > 远程配置"""

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

### 5.2 `src/configs/__init__.py`

```python
from src.configs.app_configs import Configs

configs = Configs()  # 全局单例
```

### 5.3 `example-env.yaml` 同步规则

- 分节顺序与 `Configs` 基类列表**严格一致**
- 每个字段一行注释
- 敏感字段示例值统一写 `"ENC(your_xxx)"`
- 新增 / 删除 / 移动配置字段，**必须同步更新** `example-env.yaml`

---

## 6. 数据库层（同步 SQLAlchemy）

### 6.1 设计基线

- **统一同步**：HTTP API、worker、scheduler、CRUD 全部使用同步 `sqlalchemy.orm.Session`。
- **禁止 AsyncSession** / `async def` 端点 / `await session.execute(...)`。
- **Engine 进程级单例**：每进程内只 `create_sync_engine` 一次。
- **HTTP 接口**：注入 `session: CurrentSession`，**不自动 commit**，由 service 层显式 commit。
- **Worker / scheduler**：处理一条任务 / 一个会议**只用一个 session**，统一在末尾 commit / rollback。

### 6.1.1 MySQL 同步驱动选择

| 驱动 | 驱动名 | URL 前缀 | 优势 | 劣势 |
|------|--------|----------|------|------|
| **mysqlclient** | `mysqldb` | `mysql+mysqldb://` | C 扩展，**性能最好**（比 PyMySQL 快 30%–50%）；SQLAlchemy 官方生产首选 | 需要编译，依赖系统库（Linux: `default-libmysqlclient-dev`；macOS: `mysql-client`） |
| **PyMySQL** | `pymysql` | `mysql+pymysql://` | 纯 Python，**安装零依赖**，跨平台无痛；Docker 镜像可省去 build 阶段 | 性能比 mysqlclient 慢；需配 `cryptography` 才能走 MySQL 8.0 默认的 `caching_sha2_password` 认证 |
| ~~mysql-connector-python~~ | `mysqlconnector` | — | Oracle 官方 | 与 SQLAlchemy 配合时偶有怪问题，**不推荐** |

**选型建议**：
- **生产环境** → `mysqlclient`（QPS 高时性能差距明显）
- **本地开发 / Docker 镜像追求轻量** → `PyMySQL`（配 `cryptography`）
- **团队混合环境** → 走 `MYSQL_DRIVER` 配置驱动，让本地用 `pymysql`、生产用 `mysqldb`，业务代码无感知

切换方式：仅改 `.env` 里 `MYSQL_DRIVER=mysqldb`（或 `pymysql`）+ `pyproject.toml` 依赖项二选一，业务代码无需改动。

### 6.2 `src/db/engines.py`

```python
import json
from datetime import datetime
from enum import Enum
from typing import Any

import sqlalchemy
from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from src.configs import configs
from src.utils.log import get_logger

logger = get_logger("db")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, cls=_Encoder, ensure_ascii=False)


class _Encoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def create_sync_engine(uri: str, echo: bool = False) -> sqlalchemy.Engine:
    """创建同步 Engine。

    关键参数说明：
    - pool_pre_ping=True：每次取连接发 SELECT 1 验证可用性，避免使用被 MySQL 服务端
        断开的空闲连接（云数据库 wait_timeout 经常被改小至 60-600 秒）。
    - pool_recycle=3600：主动回收空闲连接，必须**小于** MySQL `wait_timeout`，否则
        偶发 `MySQL server has gone away`（错误码 2006/2013）。
    - connect_args 三个 timeout：防止网络异常时请求线程被永久 hang 住。
    """
    return _create_sync_engine(
        url=uri,
        echo=echo,
        json_serializer=_dumps,
        pool_size=configs.POOL_SIZE,
        max_overflow=configs.POOL_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "connect_timeout": configs.DB_CONNECT_TIMEOUT,
            "read_timeout": configs.DB_READ_TIMEOUT,
            "write_timeout": configs.DB_WRITE_TIMEOUT,
        },
    )


sync_engine = create_sync_engine(configs.db_uri, echo=configs.PRINT_SQL)
SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False, expire_on_commit=False)


# ── 强制会话级 sql_mode（每个新连接生效一次）──────────────────────────────────
@event.listens_for(sync_engine, "connect")
def _set_session_sql_mode(dbapi_conn, connection_record) -> None:
    """每个新建连接强制严格 SQL 模式。

    MySQL 默认非严格模式会**静默**做以下危险事情：
    - 把超长字符串截断（VARCHAR(10) 写入 20 字符 → 只存前 10 个，无报错）
    - 把非法日期变成 '0000-00-00'（业务读出来直接报错）
    - 把字符串 `"abc"` 写入数字字段时变成 0（典型数据质量灾难）

    强制 STRICT_TRANS_TABLES 后这些情况会**直接抛错**，让问题在测试阶段就暴露。
    """
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(
            "SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,"
            "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO'"
        )
    finally:
        cursor.close()
```

#### 6.2.1 `expire_on_commit=False` 详解（重要）

`sessionmaker` 的 `expire_on_commit` 决定 **commit 后已加载 ORM 对象的命运**。本项目**关闭**（`False`），与之配套的是 service 层 "`commit()` + `refresh()` 两步走" 的规范。下面解释为什么。

**默认 `True` 的行为**：commit 后当前 session 加载过的全部 ORM 对象被标记为 `expired`，**下次访问任意属性都会自动发一发 `SELECT`** 重新拉。

```
session.add(row)      # row.id = None
session.flush()       # row.id = "abc"，row.name = "Nigeria"
row.name              # ✅ 直接读内存
session.commit()      # ← row 进入 expired 状态
row.name              # ⚠️ 触发 SELECT * FROM countries WHERE id='abc'
                      #    SQLAlchemy 默默打了一发 SQL
```

**改成 `False` 的行为**：commit 后对象保持 commit 前的内存状态，访问属性不打任何 SQL。代价是如果别的事务/Pod 改了这一行，手里的对象就是**陈旧快照**。

**对照表**：

| 维度 | `True`（SA 默认） | `False`（本项目） |
|------|-------------------|-------------------|
| commit 后访问属性 | 自动 SELECT 一次 | 直接读内存 |
| 数据新鲜度 | 强（commit 即查） | 弱（commit 时点的快照） |
| 性能 | 每次属性访问可能打 SQL | 零额外 SQL |
| 跨 commit 重用对象 | commit 即作废，需 refresh / 重读 | 可以继续用 |
| Detached（session 关闭后） | 抛 `DetachedInstanceError` | 仍可读已加载属性 |
| 心智成本 | "对象状态永远等于 DB" | "返回前手动 refresh，否则可能脏" |

**为什么本项目选 `False`**：

1. **worker / scheduler 长事务里多次 commit**：开 `True` 时每次 commit 后 ORM 对象失效，下次 `obj.field` 访问触发隐式 SELECT，一条任务可能多打几十发 SQL，性能不可控。
2. **HTTP 路径 service `commit()` 后立即 `return row`**：FastAPI 用 `model_validate(row)` 序列化时会读所有字段，开 `True` 等于多一发 SELECT。
3. **避免隐式 SQL**：每条 SQL 都来自显式调用是 debug 友好的工程取向；"读属性其实在打 SQL" 是排障最讨厌的事。

**搭配规范**：

```python
# Service 层标准写法
def create(self, session, body):
    row = xxx_crud.add(session, ...)
    session.commit()
    session.refresh(row)   # ← 需要返回 DB 权威状态时显式 refresh
    return row
```

**适用边界**：

- ✅ **必须 `False`**：worker 长事务、跨 commit 重用对象、ORM 对象直接渲染响应
- ⚠️ **可考虑 `True`**：纯 HTTP API + 团队不熟 SQLAlchemy，要"框架强制保证对象新鲜"的安全感。但更好的做法仍是保持 `False`，靠 review 兜住 service 层的 `refresh` 规范，让显式胜过隐式。

> **新项目搬本模板时**：保持 `expire_on_commit=False`，并把"service `commit()` 之后必须 `refresh(row)` 再返回"写进 review checklist。

#### 6.2.2 `sql_mode` 强制详解（重要）

`engines.py` 里的 `@event.listens_for(sync_engine, "connect")` 是**每个新连接生效一次**的 hook，强制把会话级 `sql_mode` 设成严格模式。**这一步不可省略**，原因：

**MySQL 默认 sql_mode 的 4 个静默灾难**：

| 场景 | 非严格模式（默认） | 严格模式（本项目） |
|------|-------------------|-------------------|
| `INSERT VARCHAR(10) ← "abcdefghijkl"` | 存 `"abcdefghij"`，**无报错** | 抛 `Data too long` |
| `INSERT INT ← "abc"` | 存 `0`，**无报错** | 抛 `Incorrect integer value` |
| `INSERT DATE ← "2024-13-99"` | 存 `0000-00-00`，**无报错** | 抛 `Incorrect date value` |
| `SELECT 1/0` | 返回 `NULL`，**无报错** | 抛 `Division by zero` |

**为什么用 `event listener` 而不是 my.cnf 里改？**
- 不依赖 DBA / 运维改服务端配置（开发本地、测试库、生产库可能配置不同）
- 应用代码自带配置，团队任何人启动都拿到一致行为
- DBA 重启数据库 / 改全局配置时不影响应用行为

**为什么会话级而不是全局**？
- 会话级只影响**当前连接**，不污染其他应用
- 不需要 `SUPER` 权限（`SET GLOBAL sql_mode` 需要 root，云数据库通常不给）

**5 个 mode 的作用**：

- `STRICT_TRANS_TABLES`：核心严格开关（前 3 个静默问题靠它）
- `NO_ENGINE_SUBSTITUTION`：建表时存储引擎不存在直接报错（防止 InnoDB 不可用时偷偷用 MyISAM）
- `NO_ZERO_IN_DATE` / `NO_ZERO_DATE`：禁止 `2024-00-00` / `0000-00-00` 这类合法但反人类的日期
- `ERROR_FOR_DIVISION_BY_ZERO`：除零报错（默认返回 NULL）

> **如果要排查现有连接的 sql_mode**：`SELECT @@SESSION.sql_mode;` 或 `SHOW VARIABLES LIKE 'sql_mode';`


### 6.3 `src/db/session.py`

> **设计要点**：1 份实现 + 2 个对外名字。FastAPI `Depends` 通过 `inspect.isgeneratorfunction()` 识别依赖，`@contextmanager` 装饰过的函数不被识别为 generator function，因此无法压成单一名字。
>
> - `get_db`：generator，给 FastAPI `Depends(get_db)` 或 `CurrentSession` 用。
> - `get_db_session`：`@contextmanager(get_db)` 包装，给 worker / scheduler / 脚本的 `with` 语句用。
> - **都不自动 commit**：commit 由调用方显式调用，异常自动 rollback。

```python
import contextlib
from collections.abc import Generator
from typing import Annotated, TypeAlias

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.engines import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """通用 session 工厂 — 不自动 commit；commit 由调用方显式处理，异常自动 rollback。"""
    session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


get_db_session = contextlib.contextmanager(get_db)

CurrentSession: TypeAlias = Annotated[Session, Depends(get_db)]
```

### 6.4 `src/models/base.py`（公共字段基类）

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.utils.time import TimeUtils
from src.utils.uuid import get_uuid_without_hyphen


class Base(DeclarativeBase):
    """所有表的基类，公共字段始终排在前面"""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=get_uuid_without_hyphen, comment="主键 ID")
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="租户ID")
    enable_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", comment="是否有效")
    delete_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", comment="软删标记")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="创建人")
    created_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=TimeUtils.now, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间")
    updated_by: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="更新人")
    updated_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=TimeUtils.now, server_default=text("CURRENT_TIMESTAMP"), onupdate=TimeUtils.now, comment="更新时间")
```

**Model 字段约束**：
- `mapped_column(...)` 单行写完，再长也不换行
- 索引一律放 `__table_args__` 里的 `Index(...)`，禁止字段上 `index=True`
- 所有 Enum 集中放 `models/enums.py`

#### `Mapped[X]` 与 `mapped_column()` 类型契约

字段定义有两个槽位，分工固定，不能混：

```python
created_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, ...)
#             ^^^^^^^^^^^^^^^^^^^^^^^                 ^^^^^^^^  ^^^^^^^^^^^^^
#             Python 类型层（X）                       SQL 列类型 + DDL 约束
```

| 槽位 | 决定什么 | 谁读 |
|------|---------|------|
| `Mapped[X]` 里的 X | 访问 ORM 实例字段时拿到的 Python 值类型 | mypy / IDE / SQLAlchemy 自动推断 |
| `mapped_column(SQL类型, nullable=...)` | 列的 SQL 类型 + DDL（建表、迁移、ORM 加载） | SQLAlchemy / Alembic |

**两条强制规则**：

**1. X 必须是 Python 类型，不能是 SQLAlchemy 列类型。**

```python
# ✅ 正确：X 是 datetime（标准库 Python 类型）
from datetime import datetime
from sqlalchemy import DateTime
created_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, ...)

# ❌ 错误：X 写成 DateTime（SQLAlchemy 列类型）
# 后果：所有调用 created_time.strftime(...) / + timedelta 的下游全部 mypy 报错
created_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True, ...)
```

字符串/整型/浮点同理：用 `str` / `int` / `float`，不要把 `String` / `Integer` / `DECIMAL` 写到 `Mapped[X]` 里。

**2. `nullable=True` 必须对应 `Mapped[X | None]`，`nullable=False` 必须对应 `Mapped[X]`（不含 None）。**

```python
# ✅ 可空字段：类型必须含 None
topic: Mapped[str | None] = mapped_column(String(500), nullable=True, ...)

# ✅ 非空字段：类型不含 None
meeting_id: Mapped[str] = mapped_column(String(100), nullable=False, ...)

# ❌ 错误：DDL 允许 NULL，但类型说"永远是 str"
# 后果：mypy 不会警告 .strip() / 字符串比较等 None 风险代码
topic: Mapped[str] = mapped_column(String(500), nullable=True, ...)
```

`Mapped[str]` + `nullable=True` 是矛盾写法 —— 数据库说"可能 None"，类型说"不可能 None"，mypy 顺着错误的注解放过所有 None 风险代码。

**显式写 `nullable=True/False`，不要依赖 SQLAlchemy 推断。** 双写一致才是安全的写法。

**改 `Mapped[X]` 不会触发 Alembic 迁移。** Alembic autogenerate 比对的是 `mapped_column()` 决定的 metadata 与数据库实际 schema，不读 `Mapped[X]`。修正类型注解是纯静态层面改动，跑 `uv run alembic -c src/db/alembic.ini revision --autogenerate -m "verify"` 可自证产物为空。

### 6.5 `models/__init__.py` 维护规则

```python
from src.models.base import Base                # 基础模型类
from src.models.country import Country          # 国家信息
from src.models.user import User                # 用户

__all__ = [
    "Base",        # 基础模型类
    "Country",     # 国家信息
    "User",        # 用户
]
```

`__all__` 每行一个条目 + 中文注释。新增 / 删除 model 时**必须同步更新** import 区和 `__all__`。

### 6.6 Alembic 迁移规则

- `alembic.ini` 放在 `src/db/alembic.ini`
- 在 `backend/` 目录下执行：`uv run alembic -c src/db/alembic.ini revision --autogenerate -m "xxx"`
- 应用迁移统一走 `upgrade_db.py`（含 Redis 分布式锁，多 Pod 安全）：
  ```bash
  cd backend && PYTHONIOENCODING=utf-8 PYTHONPATH=. uv run python scripts/upgrade_db.py
  ```
  - Windows 必须带 `PYTHONIOENCODING=utf-8`（避免 emoji 编码失败）
  - 必须带 `PYTHONPATH=.`（否则 `from src.configs ...` 报错）
- **迁移文件只允许 DDL，禁止 DML**。数据回填、修数写独立脚本放 `tests/scripts/`，不允许出现在 `migrations/versions/*.py` 里。

### 6.7 `BaseCrud[ModelT]` 父类

`src/cruds/base_crud.py` 提供基于 `Base` 公共字段的标准 CRUD：

```python
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import CursorResult, delete, insert, select, update
from sqlalchemy.orm import Session

from src.common.exception.errors import DBException, ErrorCode
from src.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseCrud(Generic[ModelT]):
    """通用 CRUD 父类。"""

    model: type[ModelT]

    # ── 查询 ────────────────────────────────────────────────────────────────
    def get_by_id(self, session: Session, model_id: str) -> ModelT:
        """按主键查询；找不到抛 ``DBException(NOT_FOUND)``。"""
        row = self.get_by_id_or_none(session, model_id)
        if row is None:
            raise DBException(
                f"{self.model.__name__} 不存在: id={model_id}",
                error_code=ErrorCode.NOT_FOUND,
            )
        return row

    def get_by_id_or_none(self, session: Session, model_id: str) -> ModelT | None:
        """按主键查询；找不到返回 None（用于 upsert / 创建前查重 / 占用检查）。"""
        stmt = (
            select(self.model)
            .where(self.model.id == model_id)
            .where(self.model.delete_flag.is_(False))
        )
        return session.execute(stmt).scalar_one_or_none()

    def list_all(self, session: Session) -> list[ModelT]:
        stmt = (
            select(self.model)
            .where(self.model.delete_flag.is_(False))
            .order_by(self.model.created_time.desc())
        )
        return list(session.scalars(stmt).all())

    # ── 写入 ────────────────────────────────────────────────────────────────
    def add(self, session: Session, **kwargs: Any) -> ModelT:
        row = self.model(**kwargs)
        session.add(row)
        session.flush()
        return row

    def update(self, session: Session, model_id: str, **kwargs: Any) -> ModelT:
        """按主键更新；kwargs 中值为 None 的字段会被跳过；id 不存在抛 ``DBException(NOT_FOUND)``。"""
        row = self.get_by_id(session, model_id)
        for key, value in kwargs.items():
            if value is not None:
                setattr(row, key, value)
        session.flush()
        return row

    # ── 删除 ────────────────────────────────────────────────────────────────
    def soft_delete(self, session: Session, model_id: str) -> int:
        stmt = (
            update(self.model)
            .where(self.model.id == model_id)
            .values(delete_flag=True)
        )
        return cast(CursorResult[Any], session.execute(stmt)).rowcount

    def hard_delete(self, session: Session, model_id: str) -> int:
        stmt = delete(self.model).where(self.model.id == model_id)
        return cast(CursorResult[Any], session.execute(stmt)).rowcount

    # ── 批量 ────────────────────────────────────────────────────────────────
    def bulk_create(self, session: Session, rows: list[dict]) -> None:
        session.execute(insert(self.model), rows)

    def bulk_update(self, session: Session, rows: list[dict]) -> None:
        session.execute(update(self.model), rows)

    def bulk_soft_delete(self, session: Session, ids: list[str]) -> int:
        stmt = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .values(delete_flag=True)
        )
        return cast(CursorResult[Any], session.execute(stmt)).rowcount

    def bulk_hard_delete(self, session: Session, ids: list[str]) -> int:
        stmt = delete(self.model).where(self.model.id.in_(ids))
        return cast(CursorResult[Any], session.execute(stmt)).rowcount
```

**继承约束**：
- 子类**必须**在类体里声明 `model = XxxModel`，否则父类方法无法定位表。
- 父类只放"形状一致"的方法；任何带"语义"（按 name / chat_id 查、特定排序、含 join）的查询，**留在子类**。
- 父类方法返回 ORM model 实例，不做 Pydantic 转换 —— 转换由 service 层做。

#### 单条查询：默认抛错，按需 `_or_none`

每个 `get_by_<field>` 方法**默认就是抛错版** —— 找不到抛 `DBException(NOT_FOUND)`，签名 `-> T`，**不接收 `is_raise_exception` 参数**。绝大多数业务调用（worker / scheduler / service 主流程）都属于"找不到 = bug"语义，类型层面应该是 `T` 不是 `T | None`，调用方拿到对象直接用，无需 None 检查。

**只有当业务真有"可能不存在"语义时**（upsert 前查重 / 创建前重名检查 / 探查），才在该 CRUD 里**额外**加一个同名 `_or_none` 方法，签名 `-> T | None`。判断标准：调用方需要写 `if existing: ... else: ...` 这种分支的，才需要 `_or_none`；其他一律不加。

**禁止使用 `is_raise_exception` 参数。** 这个参数把"业务分支"写进"类型可空性"，导致返回类型永远是 `T | None`，下游被迫到处 `assert` / `if not`，且 mypy 也无法准确推断。

```python
# ✅ 主流程：抛错版，类型推断为 T
meeting = meeting_crud.get_by_meeting_id(session, meeting_id)
meeting.status = "transcribing"   # 直接用，无需 None 检查

# ✅ upsert / 重名检查：调 _or_none 版，类型推断为 T | None
existing = meeting_crud.get_by_meeting_id_or_none(session, meeting_id)
if existing:
    ...  # 更新
else:
    ...  # 新建

# ❌ 错误：曾经的 is_raise_exception 模式（已废弃）
existing = meeting_crud.get_by_meeting_id(session, meeting_id, is_raise_exception=False)
```

**实现样板**：抛错版调 `_or_none` 版包一层判空抛错，stmt 只写一份。子类自定义查询同样遵循这个套路（参见 §20.3 的 `CountryCrud.get_by_name`）。

---

## 7. 分层架构规范

### 7.1 总体分层

```
HTTP Request
   ↓
Controller (controllers/api/v1/*.py)
   ├─ 注入 session: CurrentSession
   ├─ 用 @api_response(SchemaOut) 包装
   └─ 只做参数解析 + service 调用 + return
       ↓
Service (services/*_service.py)
   ├─ 类 + 单例（xxx_service = XxxService()）
   ├─ 业务编排：CRUD 组合 + 第三方 API 调用 + 事务边界
   └─ 显式 session.commit() / session.rollback()
       ↓
   ┌───────────────┴───────────────┐
   ↓                               ↓
Core (core/<domain>/，可选)      CRUD (cruds/*_crud.py)
   ├─ analyzers/                    ├─ 类 + 单例
   ├─ llm/                          ├─ 继承 BaseCrud[ModelT]
   ├─ matchers/                     ├─ 只写实体专属查询，禁止业务逻辑
   ├─ prompts/                      └─ 抛 DBException
   ├─ renderers/                       ↓
   └─ senders/                      Model (models/*.py)
```

### 7.2 Controller 模板

```python
from fastapi import APIRouter, Path

from src.common.api_response import api_response
from src.common.response.response_schema import Response
from src.db.session import CurrentSession
from src.models.country import Country
from src.schemas.admin import CountryCreate, CountryOut, CountryUpdate
from src.services.country_service import country_service

router = APIRouter(prefix="/countries", tags=["国家"])


@router.get("", summary="列出所有国家", response_model=Response[list[CountryOut]])
@api_response(list[CountryOut])
def list_countries(session: CurrentSession) -> list[Country]:
    return country_service.list_all(session)


@router.post("", summary="创建国家", response_model=Response[CountryOut])
@api_response(CountryOut)
def create_country(session: CurrentSession, body: CountryCreate) -> Country:
    return country_service.create(session, body)


@router.get("/{country_id}", summary="国家详情", response_model=Response[CountryOut])
@api_response(CountryOut)
def get_country(session: CurrentSession, country_id: str = Path(...)) -> Country:
    return country_service.get(session, country_id)


@router.delete("/{country_id}", summary="软删国家", response_model=Response[None])
@api_response()
def delete_country(session: CurrentSession, country_id: str = Path(...)) -> None:
    country_service.delete(session, country_id)
```

**Controller 三大约束**：
1. **`response_model=Response[T]` 显式声明**，让 Swagger 渲染精准
2. **`@api_response(T)` 自动**做 ORM → Pydantic + `response_base.success` 包装 + 异常分类日志
3. 业务体只写"调 service + return"，**禁止**写 try/except / model_validate / response_base

### 7.3 Service 模板

```python
from sqlalchemy.orm import Session

from src.common.exception.errors import ErrorCode, ServiceException
from src.cruds.country_crud import country_crud
from src.models.country import Country
from src.schemas.admin import CountryCreate, CountryUpdate


class CountryService:

    def list_all(self, session: Session) -> list[Country]:
        return country_crud.list_all(session)

    def get(self, session: Session, country_id: str) -> Country:
        return country_crud.get_by_id(session, country_id)

    def create(self, session: Session, body: CountryCreate) -> Country:
        # 创建前重名检查：业务上"可能不存在"语义，调 _or_none 版
        existed = country_crud.get_by_name_or_none(session, body.name)
        if existed:
            raise ServiceException(f"国家已存在: {body.name}", error_code=ErrorCode.PARAM_ERROR)
        row = country_crud.add(session, name=body.name, code=body.code)
        session.commit()
        session.refresh(row)
        return row

    def delete(self, session: Session, country_id: str) -> None:
        if country_crud.soft_delete(session, country_id) == 0:
            raise ServiceException(f"国家不存在: {country_id}", error_code=ErrorCode.NOT_FOUND)
        session.commit()


country_service = CountryService()
```

**Service 五大约束**：
1. **必须类 + 单例**：禁止写模块级函数
2. **业务异常统一抛 `ServiceException`**：禁止就地 `class XxxError(Exception)`；如需特定语义在 `errors.py` 增加子类
3. **CRUD 组合 / 第三方 API 调用 / 数据校验**全在 service
4. **commit 在 service 显式调用**：HTTP 一接口一事务，worker 一任务一事务
5. **类方法不加 `_` 前缀**：仅 `__init__` 等魔术方法保留双下划线

### 7.4 CRUD 模板

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.exception.errors import DBException, ErrorCode
from src.cruds.base_crud import BaseCrud
from src.models.country import Country


class CountryCrud(BaseCrud[Country]):
    model = Country

    def get_by_name(self, session: Session, name: str) -> Country:
        """按 name 查询；找不到抛 ``DBException(NOT_FOUND)``。"""
        row = self.get_by_name_or_none(session, name)
        if row is None:
            raise DBException(f"Country 不存在: name={name}", error_code=ErrorCode.NOT_FOUND)
        return row

    def get_by_name_or_none(self, session: Session, name: str) -> Country | None:
        """按 name 查询；找不到返回 None（用于创建前查重）。"""
        stmt = (
            select(Country)
            .where(Country.name == name)
            .where(Country.delete_flag.is_(False))
        )
        return session.execute(stmt).scalar_one_or_none()


country_crud = CountryCrud()
```

**CRUD 八条铁律**：
1. **一实体一文件 + 类 + 单例**
2. **必须用 ORM**：禁止 `session.execute(text("SELECT ..."))` 这类原生 SQL（仅 `init_db.py` 与 Alembic schema 迁移 DDL 豁免）
3. **只做 DB 封装，禁止业务逻辑**：禁止调第三方 API、读 Redis、调其他 service
4. **抛 `DBException`**（非 `ServiceException`），`NOT_FOUND` 用 `error_code=ErrorCode.NOT_FOUND` 区分
5. **统一 `get_by_<field>` 命名，默认抛错版 `-> T`，按需提供 `_or_none` 版 `-> T | None`**；**禁止** `is_raise_exception` 参数；禁止 `find_by_*` / `query_by_*` 等同义方法并存
6. **`stmt` 多行格式**：`( ... )` 包裹，每个 `.where()` 单独一行（多个条件拆成多个 `.where()`，**禁止** `.where(a, b, c)`）；`session.execute()` / `session.scalars()` 必须传具名 `stmt` 变量，禁止内联多行链式
7. **返回类型禁止裸 dict**：必须 ORM model / Pydantic / dataclass
8. **批量必须 bulk**：禁止 for-loop 逐条 add/update；MySQL UPSERT 用方言 `mysql_insert.on_duplicate_key_update(...)` 原子写入，**禁止** for-loop + try/except + `IntegrityError` 兜底

执行 API 选择表：

| 期望结果 | 执行 API | 行为 |
|---|---|---|
| 0 / 1 条 | `session.execute(stmt).scalar_one_or_none()` | 0→None；1→对象；≥2 抛 `MultipleResultsFound` |
| 必须 1 条 | `session.execute(stmt).scalar_one()` | 0 / ≥2 都抛错 |
| 多条列表 | `session.scalars(stmt).all()` | 必须配合 `order_by` |
| 多条取首条 | `session.scalars(stmt).first()` | 必须显式 `order_by` |

**禁止 `session.scalar(stmt)`**：多结果时静默返回首条，掩盖数据问题。

### 7.5 业务核心域（`src/core/`）

当业务复杂度超过"CRUD + 第三方 API 调用"时，把领域逻辑（LLM 调用、模板匹配、卡片渲染、消息发送等）从 service 抽出到 `src/core/<domain>/`，保持 service 只做"编排"。

**典型职责**：

- `analyzers/`：领域分析逻辑（如会议质量分析、GM 能力评分）
- `llm/`：LLM 客户端封装（OpenAI 协议适配、重试、限流）
- `matchers/`：模板 / 主题匹配（基于规则 + LLM）
- `prompts/`：Prompt 模板构造器
- `renderers/`：飞书卡片 / 报告渲染器
- `senders/`：消息发送适配器

**依赖方向**：service → core，**禁止反向**（core 不调 service / controller）。

**DB 访问**：core 模块原则上不直接持有 session，必要时由 service 把 session 透传进来。

**可选性**：小型项目可以不建 `src/core/`，把领域逻辑放在 service 文件里就够了。

---

## 8. 统一响应与异常体系

### 8.1 `Response[T]` 结构

所有 HTTP 响应**统一形态**：

```json
{
    "success": true,
    "code": "0",
    "message": "成功",
    "detailMessage": null,
    "data": { ... },
    "request_id": "<uuid>"
}
```

```python
from typing import TypeVar
from pydantic import BaseModel, Field

from src.common.exception.errors import ErrorCode

T = TypeVar("T")


class Response[T](BaseModel):
    success: bool = Field(True)
    code: str = Field(ErrorCode.SUCCESS.code)
    message: str = Field(ErrorCode.SUCCESS.msg)
    detailMessage: str | None = Field(None)
    data: T | None = Field(None)
```

### 8.2 错误码规范

```python
from enum import Enum


class ErrorCode(Enum):
    SUCCESS = ("0", "成功")

    # 客户端错误 4xxxxx
    PARAM_ERROR = ("400001", "参数错误")
    VALIDATION_ERROR = ("400002", "参数校验失败")
    AUTH_ERROR = ("400003", "认证失败")
    FORBIDDEN = ("400004", "权限不足")
    NOT_FOUND = ("400005", "资源不存在")
    RATE_LIMIT = ("400006", "请求过于频繁")

    # 服务端错误 5xxxxx
    SYS_ERROR = ("500001", "系统错误")
    SERVICE_ERROR = ("500002", "服务层错误")
    DB_ERROR = ("500003", "数据库错误")
    REDIS_ERROR = ("500006", "Redis错误")

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def msg(self) -> str:
        return self.value[1]
```

### 8.3 自定义异常树

`src/common/exception/errors.py` **统一**定义所有自定义异常，业务代码禁止就地 `class XxxError(Exception)`：

```python
class AppBaseException(Exception):
    def __init__(self, error_code: ErrorCode = ErrorCode.SYS_ERROR, message: str = "") -> None:
        self.error_code = error_code
        self.code = error_code.code
        self.message = message or error_code.msg


class ServiceException(AppBaseException):
    """Service 层业务异常（业务层默认抛这个）"""
    def __init__(self, message: str = "", error_code: ErrorCode = ErrorCode.SERVICE_ERROR) -> None:
        super().__init__(error_code=error_code, message=message)


class DBException(AppBaseException):
    """CRUD 层异常（含 NOT_FOUND 语义）"""
    def __init__(self, message: str = "", error_code: ErrorCode = ErrorCode.DB_ERROR) -> None:
        super().__init__(error_code=error_code, message=message)


class ParamsException(AppBaseException):
    """参数异常"""
    def __init__(self, message: str = "") -> None:
        super().__init__(error_code=ErrorCode.PARAM_ERROR, message=message)


class RedisException(AppBaseException): ...
```

### 8.4 全局 Exception Handler

`src/common/exception/exception_handler.py` 注册以下 handler，**所有错误**最终都翻译成统一 JSON 形态：

| Handler | 处理对象 | 行为 |
|---------|----------|------|
| `HTTPException` | Starlette HTTP 异常 | dev 回显 detail，prod 返回通用提示 |
| `RequestValidationError` | FastAPI 请求体校验 | 提取首个错误，dev 携带完整 errors 列表 |
| `ValidationError` | Pydantic 模型校验 | 同上 |
| `ValueError` | 业务参数非法 | 200 + business-fail 形态 |
| `AssertionError` | 断言失败 | dev 回显，prod 返回通用 |
| `AppBaseException` | 所有自定义业务异常 | 回显 `code` / `message` / `detailMessage` |
| `Exception` | 兜底 | dev 回显异常字符串，prod 返回 SYS_ERROR |

**关键设计**：业务异常都返回 HTTP 200 + body 里 `success: false`，由前端按 `code` 分类处理；只有真正的传输/网络错误才返回非 200。

### 8.5 `@api_response()` 装饰器

`src/common/api_response.py`：

```python
import functools
from typing import Any, Callable, get_args, get_origin

from pydantic import BaseModel

from src.common.exception.errors import AppBaseException
from src.common.response.response_schema import Response, response_base
from src.utils.log import get_logger

logger = get_logger("api")


def api_response(schema: Any = None) -> Callable:
    """controller 装饰器：自动 ORM→Pydantic + response_base.success 包装 + 异常分类日志"""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Response:
            try:
                raw = fn(*args, **kwargs)
                payload = to_schema(raw, schema)
                return response_base.success(data=payload)
            except AppBaseException as exc:
                logger.exception(f"[{type(exc).__name__}] {fn.__module__}.{fn.__qualname__} -> {exc.message}")
                raise
            except Exception:
                logger.exception(f"[Unexpected] {fn.__module__}.{fn.__qualname__}")
                raise

        return wrapper

    return decorator


def to_schema(data: Any, schema: Any) -> Any:
    if schema is None or data is None:
        return data
    origin = get_origin(schema)
    if origin is list:
        item_schema = get_args(schema)[0]
        return [item_schema.model_validate(item) for item in data]
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema.model_validate(data)
    return data
```

---

## 9. 中间件与日志

### 9.1 中间件注册顺序

```
[最外] CorrelationIdMiddleware     # 注入 X-Request-ID
       CORSMiddleware              # 跨域
       RequestLoggingMiddleware   # 访问日志
[最内] ErrorLoggingMiddleware     # 4xx/5xx 错误日志
       Route handler
```

### 9.2 `RequestLoggingMiddleware`

```python
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.log import get_logger

logger = get_logger("api_access", filename="api_access.log")
_SKIP_PATHS = {"/health", "/actuator/health/readiness", "/actuator/health/liveness"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = round(time.time() - start, 4)
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.4f}s")
        return response
```

### 9.3 `ErrorLoggingMiddleware`

记录所有 4xx/5xx 响应 + 未捕获异常的结构化日志（方法 / 路径 / 状态码 / 耗时）。

### 9.4 日志规则

- **统一通过 `get_logger(name, filename=None)` 获取**，按需要分文件写
- **禁止 `%s` 占位符**：必须 f-string，例 `logger.info(f"[Tag] key={val}")`
- **必须单行**：每条 `logger.xxx()` 调用必须写在同一行，禁止换行
- 进程入口最前面调用 `init_logger("<process>", "run_<process>.log")` 设置默认文件名

---

## 10. Redis 客户端与 Key 前缀

### 10.1 全局代理 + 自动前缀

`src/utils/redis.py` 提供 `redis_client` 全局包装器，自动给所有 key 加 `REDIS_KEY_PREFIX`：

```python
from src.utils.redis import redis_client

# 实际执行：SET <prefix>:lock:foo "1" EX 30 NX
redis_client.set("lock:foo", "1", ex=30, nx=True)
```

**绝对禁止**：
- `redis_client.client.xxx()` — 绕过代理，导致 key 缺前缀
- 在 `QueueKey` / `RedisKey` 常量里硬编码 prefix
- 使用白名单外的命令 — 先把命令加入 `KeyPrefixMethodProxy` 白名单再调用

### 10.2 Key 集中常量类

`src/common/redis_keys.py`：

```python
class RedisKey:
    """Redis Key 常量"""

    # ── 队列（funboost worker，需手动拼接 prefix） ────────────────────
    QUEUE_RAW_EVENTS:       str = "queue:feishu_events"
    QUEUE_BUSINESS:         str = "queue:business"

    # ── 分布式锁（redis_client 自动注入 prefix，直接使用） ──────────────
    LOCK_LEADER:            str = "lock:leader"

    # ── 业务 key（redis_client 自动注入 prefix） ────────────────────
    USER_TOKEN:             str = "user:token"  # 后缀 :{user_id}
```

**funboost 队列名**特殊：funboost 不会自动注入前缀，需手动拼接：

```python
QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_RAW_EVENTS}"
```

### 10.3 分布式锁

```python
from src.utils.redis import DistributedLock

with DistributedLock("my_critical_section", expire_time=60):
    # 临界区代码
    ...
```

或细粒度的 `RedisDistributedLockContextManager`（带文件 / 行号 trace）。

---

## 11. 异步任务与定时任务（funboost）

### 11.1 funboost worker 规范

worker 函数本身**只接受一个 `task: dict`**，业务逻辑放在 `Processor` 类里：

```python
import logging

from funboost import BoosterParams, boost
from funboost.constant import BrokerEnum, ConcurrentModeEnum

from src.common.redis_keys import RedisKey
from src.configs import configs
from src.db.session import get_db_session
from src.schemas.worker_task import MyTaskData

QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_BUSINESS}"


class MyTaskProcessor:
    def __init__(self, task_data: dict) -> None:
        self.task = MyTaskData.model_validate(task_data)  # dict→Pydantic

    def process(self) -> None:
        with get_db_session() as session:
            try:
                # 业务逻辑全部用同一个 session
                ...
                session.commit()
            except Exception:
                session.rollback()
                raise


@boost(
    BoosterParams(
        queue_name=QUEUE_NAME,
        broker_kind=BrokerEnum.REDIS_STREAM,
        concurrent_mode=ConcurrentModeEnum.THREADING,
        qps=configs.MY_WORKER_QPS,
        max_retry_times=configs.MAX_RETRIES,
        logger_name="my_worker",
        log_level=logging.ERROR,
        create_logger_file=False,
        is_push_to_dlx_queue_when_retry_max_times=True,
    )
)
def my_task(task: dict) -> None:
    MyTaskProcessor(task).process()


def enqueue_task(data: MyTaskData) -> None:
    """任务入队：上游统一调这个函数，禁止散字段 push"""
    my_task.push(data.model_dump())
```

**worker 三大约束**：
1. **并发模式固定 `THREADING`**，禁止 asyncio / gevent / eventlet
2. **入参必须是 dict**：`push` 时由 Pydantic / dataclass `model_dump()` 得到；`process` 第一步转回 model
3. **一任务一 session**：所有 DB 操作在同一个 `with get_db_session()` 块内完成

### 11.2 定时任务（`ApsJobAdder`）

**禁止**裸用 APScheduler 直接调消费函数本体（多 Pod 会重复触发）。**必须**用 funboost `ApsJobAdder` + `job_store_kind='redis'`：

```python
from funboost import ApsJobAdder

ApsJobAdder(my_scanner_task, job_store_kind="redis").add_push_job(
    trigger="interval",
    seconds=configs.MY_SCAN_INTERVAL,
    kwargs={"task": {}},
    id="my_scanner",
    replace_existing=True,
    coalesce=True,
    max_instances=1,
)
```

`ApsJobAdder` 内部用 Redis 分布式锁保证多 Pod 只有一个实例触发 schedule，触发后 push 到队列由消费者执行（消费者多 Pod 天然安全）。

### 11.3 funboost broker 配置

`backend/funboost_config.py`（必须放项目根，funboost 启动时自动读取）：

```python
import logging
from urllib.parse import quote_plus

from funboost.utils.simple_data_class import DataClassBase

from src.configs import configs


class BrokerConnConfig(DataClassBase):
    REDIS_HOST = configs.REDIS_HOST
    REDIS_USERNAME = configs.REDIS_USERNAME or ""
    REDIS_PASSWORD = configs.REDIS_PASSWORD or ""
    REDIS_PORT = configs.REDIS_PORT
    REDIS_DB = configs.REDIS_DB
    REDIS_URL = (
        f'redis://{configs.REDIS_USERNAME or ""}:{quote_plus(str(configs.REDIS_PASSWORD or ""))}'
        f'@{configs.REDIS_HOST}:{configs.REDIS_PORT}/{configs.REDIS_DB}'
    )
    REDIS_DB_FILTER_AND_RPC_RESULT = configs.REDIS_DB


class FunboostCommonConfig(DataClassBase):
    TIMEZONE = "Asia/Shanghai"
    SHOW_HOW_FUNBOOST_CONFIG_SETTINGS = False
    FUNBOOST_PROMPT_LOG_LEVEL = logging.ERROR
```

### 11.4 多 Pod 并发兜底规则

生产默认部署 ≥2 Pod，所有代码必须考虑多实例：

- **UPSERT 优先用 MySQL 方言原子写入**：需要"存在则更新、不存在则插入"语义时，统一用 `from sqlalchemy.dialects.mysql import insert as mysql_insert` 的 `on_duplicate_key_update(...)`，由 DB 内核保证原子性。**禁止** for-loop + try/except + `IntegrityError` 兜底 / 二次查的旧模式。

  ```python
  from sqlalchemy.dialects.mysql import insert as mysql_insert

  stmt = mysql_insert(Meeting).values(**fields)
  stmt = stmt.on_duplicate_key_update(
      status=stmt.inserted.status,
      end_time=stmt.inserted.end_time,
  )
  session.execute(stmt)
  ```

- **唯一约束兜底**：业务上不允许重复的字段必须在 DB 层加 `unique=True` 或 `UniqueConstraint`，不能只靠应用层 SELECT。
- **DB 幂等写入（非 upsert 场景）**：纯 INSERT（如事件日志去重）若必须先 SELECT 再 INSERT，可在 `flush()/commit()` 外捕获 `IntegrityError` 并返回幂等结果，不让异常向上传播；但能用 `INSERT IGNORE` / `on_duplicate_key_update` 表达的优先用方言。
- **无状态 Worker**：funboost worker 允许多实例并行，任务处理逻辑必须幂等。
- **分布式锁按需使用**：只有真正"全局唯一执行"的场景（如 DB 迁移、定时任务触发）才用锁；普通业务优先 DB 唯一约束 + 方言 UPSERT。

---

## 12. 部署：Docker + supervisor

### 12.1 Dockerfile

```dockerfile
FROM <your-python3.12-base>

COPY ./dist/backend/docker/sources.list /etc/apt/sources.list
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates vim supervisor \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH=/root/.local/bin/:$PATH

WORKDIR /app
COPY ./dist/backend/docker              /app/docker
COPY ./dist/backend/src                 /app/src
COPY ./dist/backend/scripts             /app/scripts
COPY ./dist/backend/tests               /app/tests
COPY ./dist/backend/.python-version     /app/
COPY ./dist/backend/pyproject.toml      /app/
COPY ./dist/backend/uv.lock             /app/
COPY ./dist/backend/funboost_config.py  /app/
COPY ./dist/backend/nb_log_config.py    /app/

RUN uv sync --frozen

# 项目导入风格 from src.xxx，PYTHONPATH 指到项目根
ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8080

COPY ./dist/backend/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD sh /entrypoint.sh ${PYTHON_OPTS}
```

### 12.2 supervisor.conf

单镜像四进程，由 supervisor 守护：

```ini
[supervisord]
nodaemon=true
logfile=/var/log/supervisord.log
pidfile=/var/run/supervisord.pid

[program:web]
command=uv run scripts/start_web.py
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/sp_web.log
stdout_logfile=/app/logs/sp_web.log
environment=PYTHONUNBUFFERED=1,APP_PORT=%(ENV_APP_PORT)s

[program:worker]
command=uv run scripts/start_worker.py
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/sp_worker.log
stdout_logfile=/app/logs/sp_worker.log
environment=PYTHONUNBUFFERED=1

[program:scheduler]
command=uv run scripts/start_scheduler.py
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/sp_scheduler.log
stdout_logfile=/app/logs/sp_scheduler.log
environment=PYTHONUNBUFFERED=1
```

### 12.3 entrypoint.sh 思路

启动顺序：
1. 等待 MySQL / Redis 可达
2. （首次部署）执行 `python scripts/init_db.py`
3. 执行 `python scripts/upgrade_db.py`（带 Redis 分布式锁，多 Pod 安全）
4. `exec /usr/bin/supervisord -c /app/docker/supervisor.conf`

---

## 13. 全局编码规范汇总

### 13.1 命名

- **统一 `snake_case`**：所有函数、方法、变量、文件名
- **类名 `PascalCase`**；常量 `UPPER_SNAKE_CASE`
- **禁止 `_` 前缀**：类方法、辅助函数、模块级函数都用公开命名（仅 `__init__` / `__str__` 等魔术方法保留）
- 单例命名 = 类名 snake_case：`country_service = CountryService()`

### 13.2 类型提示

- **所有函数参数和返回值必须有类型注解**
- 使用 Python 3.12 内建语法：`list[int]` / `dict[str, int]` / `str | None` / `X | Y`，禁止 `typing.List` / `Optional[str]`
- 泛型方法用 PEP 695：`def first[T](seq: list[T]) -> T | None:`
- 循环依赖用 `from __future__ import annotations` + `if TYPE_CHECKING:`
- **`Mapped[X]` 必须写 Python 类型**（`str` / `int` / `datetime`），不能写 SQL 列类型（`String` / `Integer` / `DateTime`）；`nullable=True` 必须 `Mapped[X | None]`，`nullable=False` 必须 `Mapped[X]`；`mapped_column()` 始终显式传 `nullable=True/False`，不依赖推断（详见 §6.4）

### 13.3 Docstring（Google Style）

- 所有函数 / 方法**必须**有 docstring（`tests/` 豁免）
- 描述正文用中文，`Args:` / `Returns:` / `Raises:` 段落标题保留英文
- 第一行一句话摘要（句末加句号）

```python
def fetch_meeting(meeting_id: str, need_speaker: bool = True) -> Meeting | None:
    """拉取指定会议的元信息。

    通过外部 API 获取会议对象，权限错误或网络异常返回 None，由上层决定降级。

    Args:
        meeting_id: 会议 ID。
        need_speaker: 是否返回发言人，默认 True。

    Returns:
        成功返回 Meeting；失败返回 None。

    Raises:
        RateLimitException: 命中接口限流。
    """
```

### 13.4 时间处理

- **统一通过 `TimeUtils`**，禁止直接 `datetime.now()` / `datetime.now(UTC)`
- 默认时区 **Asia/Shanghai**（UTC+8）
- 第三方时间戳：毫秒用 `TimeUtils.from_feishu_ms()`，秒用 `TimeUtils.from_feishu_s()`

### 13.5 数据结构

- 函数间传递结构化数据**禁止裸 dict**，统一 Pydantic `BaseModel` 或 `@dataclass`
- funboost `task.push(...)` 只传一个 dict，必须由 Pydantic / dataclass `.model_dump()` / `asdict()` 得到
- worker 入参 dict 进入 process 第一步必须转回 model
- 业务 service / crud **禁止透传裸 dict**

### 13.6 一行只做一件事

```python
# ✅ 正确
payload = to_schema(raw, schema)
return response_base.success(data=payload)

# ❌ 错误：函数嵌套调用 + 包装在同一行
return response_base.success(data=to_schema(raw, schema))
```

例外：`return foo()` / `obj.method().chain()` 这种纯链式语义不强制拆。

### 13.7 异常 raise 单行

```python
# ✅ 正确
raise ServiceException(f"国家不存在: id={country_id}", error_code=ErrorCode.NOT_FOUND)

# ❌ 错误：拆多行
raise ServiceException(
    f"国家不存在: id={country_id}",
    error_code=ErrorCode.NOT_FOUND,
)
```

### 13.8 ruff / mypy / pytest 配置

完整 `[tool.ruff]` / `[tool.mypy]` / `[tool.pytest.ini_options]` 配置见 §1.1 `pyproject.toml` 完整模板，本节不重复列出。

要点速记：
- `line-length = 120` / `target-version = "py312"`
- 启用 `E / W / F / I / C / B` 规则集；`__init__.py` 豁免 `F401`
- `quote-style = "double"`（统一双引号）
- 迁移文件目录 `src/db/migrations/versions` 整体 exclude，避免管 alembic 自动生成的代码

---

## 14. 新增一个业务模块的标准步骤

以"新增一个 `Project` 资源（含基本 CRUD）"为例，按以下顺序操作：

1. **Model**（`src/models/project.py`）
   - 继承 `Base`，字段单行 `mapped_column`，索引放 `__table_args__`
2. **`models/__init__.py`** 同步 import + `__all__` 加一行带中文注释
3. **Alembic**：`uv run alembic -c src/db/alembic.ini revision --autogenerate -m "add project table"`，检查生成的迁移文件
4. **CRUD**（`src/cruds/project_crud.py`）
   - 继承 `BaseCrud[Project]`，写实体专属查询，单例导出
5. **Schema**（`src/schemas/project.py`）
   - `ProjectCreate` / `ProjectUpdate` / `ProjectOut`，`ProjectOut` 加 `model_config = {"from_attributes": True}`
6. **Service**（`src/services/project_service.py`）
   - 类 + 单例，业务编排 + 显式 commit
7. **Controller**（`src/controllers/api/v1/project.py`）
   - `@api_response()` 包装，每个端点 `response_model=Response[T]`
8. **Mount Router**（`src/controllers/api/v1/router.py`）
   - `router.include_router(project_router)`
9. **配置**（如有新字段）
   - 在 `app_configs.py` 加字段并加入 `Configs` 基类列表
   - 同步更新 `example-env.yaml`（顺序 / 注释一致）
10. **应用迁移**：`PYTHONIOENCODING=utf-8 PYTHONPATH=. uv run python scripts/upgrade_db.py`
11. **测试**：`tests/scripts/init_data/seed_project.py` 种子数据 + 手工调用 Swagger 验证

---

## 15. 配套配置文件清单

新项目套用本模板时，**必须创建 / 配置**的文件：

| 文件 | 作用 | 必须性 |
|------|------|--------|
| `backend/pyproject.toml` | 依赖 + ruff + mypy 配置 | 必须 |
| `backend/uv.lock` | uv 锁文件 | 必须（`uv sync` 后生成） |
| `backend/.python-version` | `3.12`（pyenv / uv 用） | 必须 |
| `backend/funboost_config.py` | funboost broker 配置（必须根目录） | 用 worker 时必须 |
| `backend/nb_log_config.py` | nb_log 全局配置 | 必须 |
| `backend/example-env.yaml` | 环境变量示例 | 必须 |
| `backend/.env` | 本地实际配置（不入版本库） | 必须 |
| `backend/docker/Dockerfile` | 镜像构建 | 必须 |
| `backend/docker/entrypoint.sh` | 容器启动脚本 | 必须 |
| `backend/docker/supervisor.conf` | 多进程定义 | 必须 |
| `backend/scripts/start_web.py` | web 进程入口 | 必须 |
| `backend/scripts/start_worker.py` | worker 进程入口 | 用 worker 时必须 |
| `backend/scripts/start_scheduler.py` | scheduler 进程入口 | 用定时任务时必须 |
| `backend/scripts/init_db.py` | 建库脚本 | 必须 |
| `backend/scripts/upgrade_db.py` | 应用迁移脚本（带分布式锁） | 必须 |
| `backend/src/db/alembic.ini` | Alembic 配置 | 必须 |
| `backend/docker-compose.test.yml` | 测试 MySQL + Redis 容器（见 §22.3） | 跑自动化测试时必须 |
| `backend/tests/conftest.py` | 全局 pytest fixture（见 §22.4） | 跑自动化测试时必须 |
| `backend/tests/unit/` | 单元测试目录（见 §22.5） | 推荐 |
| `backend/tests/integration/` | 集成测试目录（见 §22.6） | 推荐 |

---

## 16. 速查清单（Cheatsheet）

### 16.1 常用命令

```bash
# 安装依赖
cd backend && uv sync --frozen

# 启动开发环境（三个进程分别启）
uv run scripts/start_web.py
uv run scripts/start_worker.py
uv run scripts/start_scheduler.py

# 数据库迁移
uv run alembic -c src/db/alembic.ini revision --autogenerate -m "add xxx"
PYTHONIOENCODING=utf-8 PYTHONPATH=. uv run python scripts/upgrade_db.py

# 数据初始化脚本（在 tests/scripts 目录下）
uv run python -m tests.scripts.init_data.seed_xxx

# 自动化测试（先起测试容器）
docker compose -f docker-compose.test.yml up -d
uv run pytest                              # 全部
uv run pytest tests/unit/                  # 仅单元测试
uv run pytest tests/integration/           # 仅集成测试
uv run pytest --cov=src --cov-report=html  # 覆盖率报告

# 代码风格检查
uv run ruff check src/
uv run ruff format src/
uv run mypy src/
```

### 16.2 必须做 / 禁止做对照

| ✅ 必须 | ❌ 禁止 |
|---------|---------|
| Service / CRUD 用类 + 单例 | 写模块级函数 |
| Controller 用 `@api_response()` | controller 里写 try/except / model_validate |
| CRUD 抛 `DBException` | CRUD 抛 `ServiceException` |
| Service 抛 `ServiceException` | 业务代码里 `class XxxError(Exception)` 就地定义 |
| `redis_client.set(key, ...)` | `redis_client.client.set(key, ...)` |
| funboost `ApsJobAdder` + `job_store_kind="redis"` | 裸 `apscheduler.add_job(consume_func, ...)` |
| worker 入参一个 dict + Pydantic 校验 | worker 接散字段 / 直接用 dict |
| 一任务 / 一接口 一 session | 同一处理流程多次 `get_db_session()` |
| `session.execute(stmt).scalar_one_or_none()` | `session.scalar(stmt)`（多结果时静默吞 bug） |
| `mapped_column(...)` 单行 | 字段定义换行 |
| 字段索引在 `__table_args__` 中 `Index(...)` | 字段上 `index=True` |
| `Mapped[X]` 写 Python 类型 + `nullable` 与 `\| None` 一致 | `Mapped[DateTime]` 或 `Mapped[str]` + `nullable=True` |
| `get_by_xxx(session, ...) -> T` 默认抛错；`_or_none` 按需提供 | `get_by_xxx(..., is_raise_exception=False)` |
| MySQL UPSERT 用 `mysql_insert.on_duplicate_key_update(...)` | for-loop + try/except + IntegrityError 兜底 |
| 迁移文件只 DDL | 迁移里写 `op.execute("UPDATE ...")` 这类 DML |
| `TimeUtils.now()` | `datetime.now()` / `datetime.now(UTC)` |
| `logger.info(f"[Tag] key={val}")` 单行 | `logger.info("msg %s", var)` 占位符或换行 |

---

## 17. 落地检查表

新项目按本模板搭建完成后，请逐项确认：

- [ ] `src/app.py` 正确注册 4 类中间件，CorrelationId 在最外
- [ ] `src/configs/app_configs.py` 多继承聚合，所有字段有 `description`
- [ ] `example-env.yaml` 与 `app_configs.py` 字段顺序、注释一致
- [ ] `src/models/base.py` 的 `Base` 含完整公共字段，`updated_time` 配 `onupdate`
- [ ] `src/cruds/base_crud.py` 提供 `get_by_id` / `get_by_id_or_none` / `list_all` / `add` / `update` / `soft/hard_delete` / `bulk_*`，`get_by_id` 默认抛错版无 `is_raise_exception` 参数
- [ ] 所有 `Mapped[X]` 注解：X 是 Python 类型（不是 SQL 列类型）；`nullable=True` 对应 `Mapped[X | None]`；`mapped_column()` 显式写 `nullable=True/False`
- [ ] MySQL UPSERT 路径统一走 `mysql_insert.on_duplicate_key_update(...)`，无 for-loop + IntegrityError 兜底
- [ ] `src/common/exception/errors.py` 集中定义所有自定义异常，`ServiceException` / `DBException` 必备
- [ ] `register_exception()` 在 `app.py` 调用
- [ ] `src/utils/redis.py` 的 `redis_client` 自动注入 `REDIS_KEY_PREFIX`
- [ ] `src/utils/time.py` 默认 Asia/Shanghai
- [ ] `funboost_config.py` 在项目根（与 `pyproject.toml` 同级）
- [ ] `scripts/start_web.py` 强制 `UVICORN_WORKER_NUM == 1`
- [ ] `scripts/upgrade_db.py` 含 Redis 分布式锁
- [ ] `docker/supervisor.conf` 拉起 web / worker / scheduler 三个进程
- [ ] `pyproject.toml` 的 `[tool.ruff]` 配置 line-length=120 / target=py312
- [ ] CI / 部署脚本里 Alembic 迁移命令带 `PYTHONIOENCODING=utf-8 PYTHONPATH=.`
- [ ] `src/db/engines.py` 注册 `@event.listens_for(engine, "connect")` 强制 `sql_mode='STRICT_TRANS_TABLES,...'`（见 §6.2.2）
- [ ] `MYSQL_DRIVER` 配置项可在 `pymysql` / `mysqldb` 间切换（见 §6.1.1）
- [ ] `connect_timeout` / `read_timeout` / `write_timeout` 都已配置
- [ ] 多 Pod 部署时，Pod 数 × 进程数 × `(POOL_SIZE + POOL_MAX_OVERFLOW)` ≤ MySQL `max_connections × 0.8`（见 §23.6）
- [ ] `tests/conftest.py` 用 savepoint 模式隔离用例（见 §22.4）
- [ ] CI 跑 `pytest` 之前先 `docker compose -f docker-compose.test.yml up -d`

---

## 附录 A：错误码使用速查

| 场景 | 抛出位置 | 异常类 | error_code |
|------|----------|--------|------------|
| 参数缺失 / 非法 | controller / service | `ParamsException` | `PARAM_ERROR` |
| Pydantic 校验失败 | 框架自动 | `RequestValidationError` | `VALIDATION_ERROR` |
| 资源不存在（按 ID 查不到） | CRUD | `DBException(NOT_FOUND)` | `NOT_FOUND` |
| 资源不存在（业务语义） | service | `ServiceException(NOT_FOUND)` | `NOT_FOUND` |
| 业务规则不满足（如已存在） | service | `ServiceException(PARAM_ERROR)` | `PARAM_ERROR` |
| 数据库操作失败 | CRUD | `DBException` | `DB_ERROR` |
| Redis 操作失败 | utils / service | `RedisException` | `REDIS_ERROR` |
| 系统未知错误 | 兜底 | `Exception` → 全局 handler | `SYS_ERROR` |

---

## 附录 B：常见反模式（Anti-pattern）

```python
# ❌ Controller 里写 try / except / 手动包装
@router.get("/{id}")
def get_country(session: CurrentSession, id: str):
    try:
        row = country_crud.get_by_id(session, id)
        if not row:
            return response_base.fail(...)
        return response_base.success(data=CountryOut.model_validate(row))
    except Exception as e:
        return response_base.fail(detail_message=str(e))

# ✅ 正解：装饰器 + 业务异常
@router.get("/{id}", response_model=Response[CountryOut])
@api_response(CountryOut)
def get_country(session: CurrentSession, id: str = Path(...)) -> Country:
    return country_service.get(session, id)
```

```python
# ❌ Service 里就地定义异常
class UserNotFoundError(Exception): ...

class UserService:
    def get(self, session, uid):
        u = user_crud.get_by_id_or_none(session, uid)
        if not u:
            raise UserNotFoundError(uid)
        return u

# ✅ 正解：统一在 errors.py，service 直接调抛错版 CRUD（NOT_FOUND 由 CRUD 抛 DBException）
from src.common.exception.errors import ServiceException, ErrorCode

class UserService:
    def get(self, session, uid):
        # CRUD 默认抛错版：找不到由 CRUD 抛 DBException(NOT_FOUND)，
        # service 不需要再判 None；返回类型推断为 User，可直接用。
        return user_crud.get_by_id(session, uid)
```

```python
# ❌ Worker 一次处理开多次 session
def process_one_meeting(meeting_id: str):
    with get_db_session() as s1:
        meeting = meeting_crud.get_by_id(s1, meeting_id)
    with get_db_session() as s2:
        meeting_crud.update_status(s2, meeting_id, "processing")
    with get_db_session() as s3:
        ...

# ✅ 正解：一任务一 session
def process_one_meeting(meeting_id: str):
    with get_db_session() as session:
        try:
            meeting = meeting_crud.get_by_id(session, meeting_id)
            meeting_crud.update_status(session, meeting_id, "processing")
            ...
            session.commit()
        except Exception:
            session.rollback()
            raise
```

```python
# ❌ Redis 绕过代理 / 队列名硬编码 prefix
redis_client.client.set("my_key", "1")
QUEUE_NAME = "myapp_dev:queue:business"

# ✅ 正解：通过代理调用 / 队列名运行时拼接
redis_client.set("my_key", "1")
QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_BUSINESS}"
```

---

## 18. `common/` 模块完整代码

> 框架基础设施，**直接整包拷贝即可使用**，无业务耦合。前面已展示过的（`api_response.py` / `response/response_schema.py` / `exception/errors.py` / `exception/exception_handler.py`）不再重复，本节补全剩余文件。

### 18.1 `src/common/constants.py`

集中存放路径常量与跨模块业务常量。

```python
import os
import sys
from pathlib import Path

current_path = Path(__file__)

COMMON_PATH = current_path.parent
SRC_PATH = COMMON_PATH.parent
DB_PATH = SRC_PATH / "db"
SCRIPTS_PATH = SRC_PATH / "scripts"

ROOT_PATH = SRC_PATH.parent
sys.path.append(str(ROOT_PATH))

ENV_PATH = ROOT_PATH / ".env"

LOGS_PATH = ROOT_PATH / "logs"
os.makedirs(LOGS_PATH, exist_ok=True)

# 时间配置
DATETIME_TIMEZONE: str = "Asia/Shanghai"
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT: str = "%Y-%m-%d"
```

### 18.2 `src/common/redis_keys.py`

```python
"""Redis Key 常量类

统一管理项目中所有 Redis Key。

- 队列 Key（QUEUE_*）：funboost 不自动注入 prefix，使用时需手动拼接：
      QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_XXX}"

- 锁 Key（LOCK_*）/ 业务 Key：redis_client 自动注入 prefix，直接传值即可：
      redis_client.lock(name=RedisKey.LOCK_XXX)
"""


class RedisKey:
    # ── 业务队列（funboost worker，需手动拼接 prefix） ──────────────────────────
    QUEUE_RAW_EVENTS:       str = "queue:raw_events"
    QUEUE_BUSINESS:         str = "queue:business"

    # ── Scanner 调度队列（ApsJobAdder push → scheduler 进程 consume） ────────
    QUEUE_SCANNER_RECORDING:     str = "queue:scanner:recording"
    QUEUE_SCANNER_TRANSCRIPT:    str = "queue:scanner:transcript"

    # ── 分布式锁（自动注入 prefix） ───────────────────────────────────────────
    LOCK_LEADER:            str = "lock:leader"

    # ── 业务 key（自动注入 prefix） ───────────────────────────────────────────
    USER_TOKEN:             str = "user:token"          # 后缀 :{user_id}
    OAUTH_STATE:            str = "oauth:state"         # 后缀 :{state}, TTL=10min
    AUTH_REQUEST_SENT:      str = "auth:request_sent"   # 后缀 :{user_id}, 一次去重标记
```

### 18.3 `src/common/response/response_code.py`

HTTP / WebSocket 标准状态码常量 + `CustomResponse` 数据类。

```python
import dataclasses
from enum import Enum


class CustomCodeBase(Enum):
    """自定义状态码基类"""

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def msg(self) -> str:
        return self.value[1]


@dataclasses.dataclass
class CustomResponse:
    """开放式响应状态码（避免 Enum 限制）"""
    code: str
    msg: str


class StandardResponseCode:
    """标准 HTTP 状态码常量"""

    SUCCESS = 200
    HTTP_201 = 201
    HTTP_204 = 204
    HTTP_301 = 301
    HTTP_302 = 302
    HTTP_400 = 400
    HTTP_401 = 401
    HTTP_403 = 403
    HTTP_404 = 404
    HTTP_405 = 405
    HTTP_409 = 409
    HTTP_422 = 422
    HTTP_429 = 429
    HTTP_500 = 500
    HTTP_502 = 502
    HTTP_503 = 503
    HTTP_504 = 504

    # WebSocket
    WS_1000 = 1000
    WS_1011 = 1011
    WS_3000 = 3000
    WS_3003 = 3003
```

### 18.4 `src/common/__init__.py` 与子目录 `__init__.py`

子目录的 `__init__.py` 保持空，或写显式 re-export：

```python
# src/common/__init__.py
# 留空即可

# src/common/response/__init__.py
from src.common.response.response_schema import Response, ResponseBase, response_base
from src.common.response.response_code import StandardResponseCode, CustomResponse

__all__ = ["Response", "ResponseBase", "response_base", "StandardResponseCode", "CustomResponse"]

# src/common/exception/__init__.py
from src.common.exception.errors import (
    AppBaseException,
    DBException,
    ErrorCode,
    ParamsException,
    RedisException,
    ServiceException,
)
from src.common.exception.exception_handler import register_exception

__all__ = [
    "AppBaseException", "ErrorCode", "ParamsException", "ServiceException",
    "DBException", "RedisException", "register_exception",
]
```

### 18.5 `src/common/context.py`

封装 `starlette_context` 的类型化访问协议，让 trace_id / 客户端 IP / 请求计时等上下文有 IDE 提示。

```python
from datetime import datetime
from typing import Any, Protocol

from starlette_context.ctx import _Context, context


class TypedContextProtocol(Protocol):
    perf_time: float
    start_time: datetime

    ip: str
    country: str | None
    region: str | None
    city: str | None

    user_agent: str
    os: str | None
    browser: str | None
    device: str | None

    permission: str | None


class TypedContext(TypedContextProtocol, _Context):
    def __getattr__(self, name: str) -> Any:
        return context.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        context[name] = value


ctx = TypedContext()
```

### 18.6 `src/common/dataclasses.py`

跨模块通用 `@dataclass`（如 Snowflake ID 信息）。集中存放避免循环 import。

```python
import dataclasses


@dataclasses.dataclass
class SnowflakeInfo:
    timestamp: int
    datetime: str
    cluster_id: int
    node_id: int
    sequence: int
```

### 18.7 `src/common/enums.py`

枚举基类，提供 `get_member_keys` / `get_member_values` / `get_member_dict` 通用方法，业务枚举继承使用。

```python
from enum import Enum
from enum import IntEnum as SourceIntEnum
from enum import StrEnum as SourceStrEnum
from typing import Any, TypeVar

T = TypeVar("T", bound=Enum)


class _EnumBase:
    """枚举基类，提供通用方法"""

    @classmethod
    def get_member_keys(cls) -> list[str]:
        """获取枚举成员名称列表"""
        return list(cls.__members__.keys())

    @classmethod
    def get_member_values(cls) -> list:
        """获取枚举成员值列表"""
        return [item.value for item in cls.__members__.values()]

    @classmethod
    def get_member_dict(cls) -> dict[str, Any]:
        """获取枚举成员字典"""
        return {name: item.value for name, item in cls.__members__.items()}


class IntEnum(_EnumBase, SourceIntEnum):
    """整型枚举基类"""


class StrEnum(_EnumBase, SourceStrEnum):
    """字符串枚举基类"""
```

### 18.8 `src/common/pagination.py` 与 `src/common/schemas/pagination.py`

基于 `fastapi-pagination` 的标准分页实现 + 对应 Pydantic schema。统一 page / size 入参、链接生成与响应壳。

`src/common/pagination.py`：

```python
from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import TYPE_CHECKING, TypeVar

from fastapi import Depends, Query
from fastapi_pagination import pagination_ctx
from fastapi_pagination.bases import AbstractPage, AbstractParams, RawParams
from fastapi_pagination.links.bases import create_links
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from typing import Self

T = TypeVar("T")
SchemaT = TypeVar("SchemaT")


class _CustomPageParams(BaseModel, AbstractParams):
    """自定义分页参数"""

    page: int = Query(1, ge=1, description="页码")
    size: int = Query(20, gt=0, le=200, description="每页数量")

    def to_raw_params(self) -> RawParams:
        return RawParams(
            limit=self.size,
            offset=self.size * (self.page - 1),
        )


class _Links(BaseModel):
    """分页链接"""

    first: str = Field(description="首页链接")
    last: str = Field(description="尾页链接")
    self: str = Field(description="当前页链接")
    next: str | None = Field(None, description="下一页链接")
    prev: str | None = Field(None, description="上一页链接")


class _PageDetails(BaseModel):
    """分页详情"""

    items: list = Field([], description="当前页数据列表")
    total: int = Field(description="数据总条数")
    page: int = Field(description="当前页码")
    size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    links: _Links = Field(description="分页链接")


class _CustomPage[T](_PageDetails, AbstractPage[T]):
    """自定义分页类"""

    __params_type__ = _CustomPageParams

    @classmethod
    def create(
        cls,
        items: list,
        params: _CustomPageParams,
        total: int = 0,
    ) -> Self:
        page = params.page
        size = params.size
        total_pages = ceil(total / size)
        links = create_links(
            first={"page": 1, "size": size},
            last={"page": total_pages, "size": size} if total > 0 else {"page": 1, "size": size},
            next={"page": page + 1, "size": size} if (page + 1) <= total_pages else None,
            prev={"page": page - 1, "size": size} if (page - 1) >= 1 else None,
        ).model_dump()

        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            links=links,
        )


class PageData[SchemaT](_PageDetails):
    """包含返回数据 schema 的统一返回模型，仅适用于分页接口"""

    items: Sequence[SchemaT]


# 分页依赖注入
DependsPagination = Depends(pagination_ctx(_CustomPage))
```

`src/common/schemas/pagination.py`（轻量版 Pydantic 入参/出参 schema，独立于 fastapi-pagination 使用）：

```python
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=200, description="每页条数")


class PageData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

### 18.9 `src/common/schema.py`

通用 Pydantic 类型与基础模型配置：`CustomPhoneNumber`（中国手机号正则）、`CustomEmailStr`（增强校验）、`SchemaBase`（统一 datetime / date 序列化）。在 service / schemas 模块复用。

```python
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, validate_email

from src.utils.time import TimeUtils

CustomPhoneNumber = Annotated[str, Field(pattern=r"^1[3-9]\d{9}$")]


class CustomEmailStr(EmailStr):
    """自定义邮箱类型"""

    @classmethod
    def _validate(cls, input_value: str, /) -> str:
        return None if not input_value else validate_email(input_value)[1]


class SchemaBase(BaseModel):
    """基础模型配置"""

    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda x: TimeUtils.to_date_time_str(x),
            date: lambda x: TimeUtils.to_date_time_str(x),
        },
    )


def ser_string(value: Any) -> str | None:
    if value:
        return str(value)
    return value
```

> **注**：项目当前同时存在 `src/common/error.py`（旧错误码 + `AppBaseException` 简版）与 `src/common/exception/errors.py`（v2 模板规范的统一异常树）。两者职责重叠，属于历史技术债，**模板不收录 `error.py`** —— 新项目按 §8 / §18.4 走统一 `exception/` 即可。

---

## 19. `utils/` 模块完整代码

### 19.1 `src/utils/log.py`

基于 `nb_log` 的全局 logger 工厂，支持按 logger 名分文件、按全局上下文设置默认。

```python
import logging
import os
from pathlib import Path

from nb_log import get_logger as get_nb_logger

from src.common.constants import LOGS_PATH

# 全局日志上下文：进程入口 init_logger() 设置后，后续 get_logger() 默认使用
_global_log_context: dict = {"default_filename": "app.log", "log_path": LOGS_PATH, "log_level": None}

DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")


class ActuatorHealthFilter(logging.Filter):
    """过滤 actuator 健康检查接口的访问日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "getMessage"):
            message = record.getMessage()
            actuator_paths = ["/actuator/health/readiness", "/actuator/health/liveness"]
            for path in actuator_paths:
                if path in message:
                    return False
        return True


def init_logger(
    app_name: str,
    log_filename: str | None = None,
    log_path: str | None = None,
    log_level: str | int | None = None,
) -> None:
    """初始化全局日志上下文。各进程入口（start_*.py）最前面调用一次。"""
    global _global_log_context
    _global_log_context["default_filename"] = log_filename or f"{app_name}.log"
    _global_log_context["log_path"] = log_path or LOGS_PATH
    _global_log_context["log_level"] = log_level


def get_logger(
    logger_name: str = "app",
    filename: str | Path | None = None,
    log_level: str | int | None = None,
):
    """获取 logger（filename 缺省取自全局上下文）。"""
    if filename is None:
        filename = _global_log_context["default_filename"]

    if log_level is None:
        log_level = _global_log_context.get("log_level") or DEFAULT_LOG_LEVEL

    if isinstance(log_level, str):
        log_level_int = logging.getLevelNamesMapping().get(log_level, logging.DEBUG)
    elif isinstance(log_level, int):
        log_level_int = log_level
    else:
        log_level_int = logging.DEBUG

    logdir = _global_log_context["log_path"]
    logger = get_nb_logger(logger_name, log_path=logdir, log_filename=filename, log_level_int=log_level_int)

    # 只在第一次调用时配置访问日志过滤器，避免重复添加
    if not hasattr(get_logger, "_access_filter_configured"):
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.addFilter(ActuatorHealthFilter())
        get_logger._access_filter_configured = True

    return logger
```

### 19.2 `src/utils/uuid.py`

```python
import uuid


def get_uuid_without_hyphen() -> str:
    """生成不带连字符的 UUID（32 位 hex）。Model 主键默认值。"""
    return uuid.uuid4().hex


def generate_uuid() -> str:
    """带连字符的标准 UUID4。"""
    return str(uuid.uuid4())
```

### 19.3 `src/utils/time.py`

```python
"""时间工具类（统一北京时间，禁止直接 datetime.now()）"""
from datetime import datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class TimeUtils:

    @staticmethod
    def now() -> datetime:
        """当前北京时间（带时区）"""
        return datetime.now(BEIJING_TZ)

    @staticmethod
    def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """当前北京时间格式化字符串"""
        return TimeUtils.now().strftime(fmt)

    @staticmethod
    def utc_now() -> datetime:
        """当前 UTC 时间（带时区）"""
        return datetime.now(ZoneInfo("UTC"))

    @staticmethod
    def from_feishu_ms(ms: str | int) -> datetime:
        """毫秒时间戳 → 北京时间 datetime（飞书 header.create_time 用）"""
        return datetime.fromtimestamp(int(ms) / 1000, tz=BEIJING_TZ)

    @staticmethod
    def from_feishu_s(s: str | int) -> datetime:
        """秒级时间戳 → 北京时间 datetime（飞书 meeting.end_time 等用）"""
        return datetime.fromtimestamp(int(s), tz=BEIJING_TZ)

    @staticmethod
    def from_feishu_time(value: str | int | datetime) -> datetime:
        """自动识别秒/毫秒/ISO 字符串 → 北京时间 datetime。解析失败抛错。"""
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=BEIJING_TZ)

        if isinstance(value, int):
            return TimeUtils.from_feishu_ms(value) if len(str(abs(value))) >= 13 else TimeUtils.from_feishu_s(value)

        if not isinstance(value, str):
            raise TypeError(f"unsupported time type: {type(value)!r}")

        raw = value.strip()
        if not raw:
            raise ValueError("empty time value")

        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            ts = int(raw)
            return TimeUtils.from_feishu_ms(ts) if len(str(abs(ts))) >= 13 else TimeUtils.from_feishu_s(ts)

        normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            return dt.astimezone(BEIJING_TZ) if dt.tzinfo else dt.replace(tzinfo=BEIJING_TZ)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=BEIJING_TZ)
            except ValueError:
                continue

        raise ValueError(f"unsupported time value: {value}")

    @staticmethod
    def to_date_time_str(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str | None:
        """datetime → 字符串；None 返回 None"""
        if dt is None:
            return None
        return dt.strftime(fmt)
```

### 19.4 `src/utils/trace_id.py`

```python
"""Request ID / Trace ID 工具（基于 asgi-correlation-id）"""
from asgi_correlation_id import correlation_id

from src.utils.uuid import get_uuid_without_hyphen


def get_request_id() -> str:
    """获取当前请求的 request_id；不在请求上下文时生成新 ID。"""
    cid = correlation_id.get()
    return cid if cid else get_uuid_without_hyphen()
```

### 19.5 `src/utils/serializers.py`

msgspec 高性能 JSON 响应（FastAPI 全局响应类）。

```python
import json
from datetime import datetime
from enum import Enum
from typing import Any

import msgspec
from starlette.responses import Response


def json_dumps(obj: Any) -> str:
    """带缩进的 JSON 序列化，处理 datetime / Enum"""
    return json.dumps(obj, cls=_Encoder, ensure_ascii=False, indent=2)


class _Encoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class MsgSpecJSONResponse(Response):
    """基于 msgspec 的高性能 JSON 响应类"""

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return msgspec.json.encode(content)
```

### 19.6 `src/utils/observe.py`

Phoenix tracing 进程级单例（可选；不接 Phoenix 时整文件可省略）。

```python
"""Phoenix tracing 初始化（失败不影响主流程）"""
from __future__ import annotations

import os

from src.configs import configs
from src.utils.log import get_logger

logger = get_logger("observe")

_global_tracer = None
_initialized: bool = False


def init_phoenix(service_name: str = "unknown") -> None:
    """注册 Phoenix tracer provider 并启用 OpenAI 自动埋点。

    Args:
        service_name: 进程名（web / worker / scheduler），作为 OTel
            service.name resource attribute，用于在同一项目下区分进程。
    """
    global _initialized, _global_tracer
    if _initialized:
        return
    try:
        if not configs.PHOENIX_ENABLED:
            logger.warning("[Phoenix] PHOENIX_ENABLED=false，跳过初始化")
            return
        endpoint = configs.PHOENIX_COLLECTOR_ENDPOINT
        if not endpoint:
            logger.warning("[Phoenix] PHOENIX_COLLECTOR_ENDPOINT 为空，跳过初始化")
            return

        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = endpoint

        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register

        project_name = configs.PHOENIX_PROJECT_NAME
        tracer_provider = register(project_name=project_name, endpoint=f"{endpoint}/v1/traces")
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

        _global_tracer = tracer_provider.get_tracer(project_name)
        _initialized = True
        logger.info(f"[Phoenix] init success service={service_name}")
    except Exception as e:
        logger.warning(f"[Phoenix] init failed (忽略，不影响主流程): {e}")


def get_tracer():
    """获取全局 tracer；未初始化或失败返回 None"""
    return _global_tracer
```

### 19.7 `src/utils/redis.py`（精简核心版）

完整代码较长（含 Sentinel / Cluster / SSL / Client-Side Cache 全套），下方是去掉边角后的**最小可用核心**。把它放到 `src/utils/redis.py`，需要 Sentinel / Cluster 时再扩 `_create_xxx_client()` 三个工厂函数即可。

```python
"""Redis 客户端：自动 key 前缀代理 + 分布式锁"""
from __future__ import annotations

import functools
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

import redis
from redis import RedisError
from redis.lock import Lock

from src.configs import configs
from src.utils.log import get_logger

logger = get_logger("redis")

T = TypeVar("T")


class KeyPrefixMethodProxy[T]:
    """Redis 方法代理，自动给 key 加前缀（白名单内的方法才注入）"""

    PREFIX_METHODS = frozenset({
        "get", "set", "delete", "exists", "expire", "ttl", "incr", "decr",
        "hget", "hset", "hdel", "hgetall", "hmget", "hmset",
        "lpush", "rpush", "lpop", "rpop", "llen", "lrange",
        "sadd", "srem", "smembers", "scard", "sismember",
        "zadd", "zrem", "zrange", "zcard", "zscore", "zremrangebyscore",
        "setex", "setnx", "getdel", "lock",
        "xadd", "xlen", "xrange", "xrevrange", "xread", "xtrim", "xdel",
    })

    def __init__(self, client: T, prefix: str | None) -> None:
        self._client = client
        self._prefix = prefix

    def _add_prefix(self, key: str | bytes) -> str | bytes:
        if not self._prefix:
            return key
        if isinstance(key, bytes):
            return self._prefix.encode("utf-8") + b":" + key
        return f"{self._prefix}:{key}"

    def _add_prefix_to_keys(self, *args: Any, **kwargs: Any) -> tuple[tuple, dict]:
        new_args = list(args)
        if new_args and isinstance(new_args[0], (str, bytes)):
            new_args[0] = self._add_prefix(new_args[0])
        new_kwargs = dict(kwargs)
        for k in ("name", "key"):
            if k in new_kwargs and isinstance(new_kwargs[k], (str, bytes)):
                new_kwargs[k] = self._add_prefix(new_kwargs[k])
        return tuple(new_args), new_kwargs

    def __getattr__(self, item: str) -> Any:
        attr = getattr(self._client, item)
        if callable(attr) and item in self.PREFIX_METHODS:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                a, k = self._add_prefix_to_keys(*args, **kwargs)
                return attr(*a, **k)
            return wrapper
        return attr


class RedisClientWrapper:
    """支持延迟初始化的 Redis 客户端包装器"""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._prefix: str | None = None

    def initialize(self, client: redis.Redis, prefix: str | None = None) -> None:
        if self._client is None:
            self._client = client
        if prefix is not None:
            self._prefix = prefix

    def __getattr__(self, item: str) -> Any:
        if self._client is None:
            raise RuntimeError("Redis client is not initialized. Call init_redis first.")
        if self._prefix is not None:
            return getattr(KeyPrefixMethodProxy(self._client, self._prefix), item)
        return getattr(self._client, item)


redis_client: RedisClientWrapper = RedisClientWrapper()


def _create_standalone_client() -> redis.Redis:
    pool = redis.ConnectionPool(
        host=configs.REDIS_HOST,
        port=configs.REDIS_PORT,
        db=configs.REDIS_DB,
        username=configs.REDIS_USERNAME or None,
        password=configs.REDIS_PASSWORD or None,
        encoding="utf-8",
        decode_responses=False,
    )
    return redis.Redis(connection_pool=pool)


def init_redis() -> None:
    """初始化全局 redis_client（在每个进程入口调用一次）"""
    try:
        client = _create_standalone_client()
        redis_client.initialize(client, prefix=configs.REDIS_KEY_PREFIX)
        logger.info(f"[Redis] 客户端初始化完成 host={configs.REDIS_HOST}:{configs.REDIS_PORT} prefix={configs.REDIS_KEY_PREFIX}")
    except Exception as e:
        logger.exception(f"[Redis] 初始化失败: {e}")
        raise


def redis_fallback(default_return: Any = None) -> Callable:
    """Redis 操作异常装饰器；失败返回默认值。"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except RedisError as e:
                logger.warning(f"Redis op failed in {func.__name__}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator


class DistributedLock:
    """基于 Redis 的分布式锁（context manager / 显式 acquire 两种用法）"""

    def __init__(self, lock_name: str, expire_time: int = 600) -> None:
        self.lock_name = lock_name
        self.expire_time = expire_time
        self._lock: Lock | None = None
        self._acquired = False

    def acquire(self, timeout: int = 10) -> bool:
        try:
            self._lock = redis_client.lock(name=self.lock_name, timeout=self.expire_time, blocking_timeout=timeout)
            if self._lock.acquire(blocking=True, blocking_timeout=timeout):
                self._acquired = True
                return True
            return False
        except Exception as e:
            logger.exception(f"获取锁失败: {self.lock_name}, {e}")
            return False

    def release(self) -> bool:
        if not self._acquired or not self._lock:
            return False
        try:
            self._lock.release()
            self._acquired = False
            return True
        except Exception as e:
            logger.warning(f"释放锁失败: {self.lock_name}, {e}")
            return False

    def __enter__(self) -> DistributedLock:
        if not self.acquire():
            raise RuntimeError(f"无法获取锁: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
```

### 19.8 `src/utils/json.py`

JSON 解析与编码扩展：

- **`parse_json_markdown(text)`**：从 LLM 返回里宽容地解析 JSON（处理 markdown 围栏、未转义换行、partial JSON、`json_repair` 兜底）
- **`CustomJSONEncoder`**：通用 JSON encoder，支持 `datetime` / Pydantic / SQLAlchemy 模型自动序列化
- **`json_dumps(data)`**：基于 `CustomJSONEncoder` 的便捷封装，输出缩进 + 非 ASCII 友好

```python
from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from json_repair import loads


def _replace_new_line(match: re.Match[str]) -> str:
    value = match.group(2)
    value = re.sub(r"\n", r"\\n", value)
    value = re.sub(r"\r", r"\\r", value)
    value = re.sub(r"\t", r"\\t", value)
    value = re.sub(r'(?<!\\)"', r"\"", value)

    return match.group(1) + value + match.group(3)


def _custom_parser(multiline_string: str) -> str:
    """LLM 返回的 action_input 可能含未转义的换行 / 制表 / 引号，统一转义。"""
    if isinstance(multiline_string, (bytes, bytearray)):
        multiline_string = multiline_string.decode()

    multiline_string = re.sub(
        r'("action_input"\:\s*")(.*?)(")',
        _replace_new_line,
        multiline_string,
        flags=re.DOTALL,
    )

    return multiline_string


# Adapted from https://github.com/KillianLucas/open-interpreter/blob/5b6080fae1f8c68938a1e4fa8667e3744084ee21/interpreter/utils/parse_partial_json.py
# MIT License


def parse_partial_json(s: str, *, strict: bool = False) -> Any:
    """解析可能缺少结尾大括号的 JSON 字符串。"""
    try:
        return json.loads(s, strict=strict)
    except json.JSONDecodeError:
        pass

    new_chars = []
    stack = []
    is_inside_string = False
    escaped = False

    for char in s:
        if is_inside_string:
            if char == '"' and not escaped:
                is_inside_string = False
            elif char == "\n" and not escaped:
                char = "\\n"
            elif char == "\\":
                escaped = not escaped
            else:
                escaped = False
        else:
            if char == '"':
                is_inside_string = True
                escaped = False
            elif char == "{":
                stack.append("}")
            elif char == "[":
                stack.append("]")
            elif char in {"}", "]"}:
                if stack and stack[-1] == char:
                    stack.pop()
                else:
                    return None

        new_chars.append(char)

    if is_inside_string:
        if escaped:
            new_chars.pop()
        new_chars.append('"')

    stack.reverse()

    while new_chars:
        try:
            return json.loads("".join(new_chars + stack), strict=strict)
        except json.JSONDecodeError:
            new_chars.pop()

    return json.loads(s, strict=strict)


_json_markdown_re = re.compile(r"```json(.*)```", re.DOTALL)
_json_markdown_re_fallback = re.compile(r"```(.*)```", re.DOTALL)
_json_strip_chars = " \n\r\t`"


def _parse_json(json_str: str, *, parser: Callable[[str], Any] = parse_partial_json) -> dict:
    json_str = json_str.strip(_json_strip_chars)
    json_str = _custom_parser(json_str)
    return parser(json_str)


def real_parse_json_markdown(json_string: str, *, parser: Callable[[str], Any] = parse_partial_json) -> dict:
    """从 markdown 字符串里解析 JSON。"""
    try:
        return _parse_json(json_string, parser=parser)
    except json.JSONDecodeError:
        match = _json_markdown_re.search(json_string)
        if match is None:
            match = _json_markdown_re_fallback.search(json_string)
        json_str = json_string if match is None else match.group(1)
        return _parse_json(json_str, parser=parser)


def parse_json_markdown(text: str) -> Any:
    """LLM 返回 JSON 的入口函数：先尝试常规解析，失败则反斜杠转义重试，再失败用 json_repair 兜底。"""
    try:
        try:
            text = text.strip()
            result = real_parse_json_markdown(text)
        except Exception:
            text = text.replace("\\", "\\\\")
            try:
                result = real_parse_json_markdown(text)
            except Exception:
                result = loads(text)
        return result
    except Exception as e:
        print(f"解析 markdown 中的 json 失败，text:\n{text}, error: {str(e)}")
        raise e


class CustomJSONEncoder(json.JSONEncoder):
    """通用 JSON encoder：支持 datetime / Pydantic / SQLAlchemy。"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")

        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                return f"<{type(obj).__name__} object (model_dump failed)>"

        if hasattr(obj, "__table__"):
            try:
                if hasattr(obj, "to_dict"):
                    return obj.to_dict()
                else:
                    return {c.name: _safe_serialize_for_json(getattr(obj, c.name)) for c in obj.__table__.columns}
            except Exception:
                return f"<{type(obj).__name__} object (SQLAlchemy serialization failed)>"

        try:
            return str(obj)
        except Exception:
            return f"<{type(obj).__name__} object (not serializable)>"


def _safe_serialize_for_json(value):
    """为 JSON encoder 安全序列化值。"""
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, (list, tuple)):
        return [_safe_serialize_for_json(item) for item in value]
    elif isinstance(value, dict):
        return {k: _safe_serialize_for_json(v) for k, v in value.items()}
    else:
        try:
            return str(value)
        except Exception:
            return f"<{type(value).__name__} object (not serializable)>"


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=4, cls=CustomJSONEncoder)
```

> 依赖项：`json-repair`（在 `pyproject.toml` `dependencies` 里加 `json-repair>=0.20`，仅当业务需要从 LLM 返回中宽容解析 JSON 时引入）。

### 19.9 `src/utils/debug_logger.py`

调试专用 logger：默认禁用、按全局开关动态打开/关闭；不进入 nb_log 主路由，避免污染生产日志。本地排障 / 灰度阶段使用。

```python
import logging
import sys

from src.common.constants import LOGS_PATH

# 全局调试开关
_DEBUG_ENABLED = False
# 存储所有创建的调试 logger
_DEBUG_LOGGERS: dict[str, logging.Logger] = {}


def enable_debug_logger() -> None:
    """启用调试日志。"""
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = True

    for logger in _DEBUG_LOGGERS.values():
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)


def disable_debug_logger() -> None:
    """禁用调试日志。"""
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = False

    for logger in _DEBUG_LOGGERS.values():
        logger.setLevel(logging.CRITICAL + 1)
        for handler in logger.handlers:
            handler.setLevel(logging.CRITICAL + 1)


def is_debug_enabled() -> bool:
    """检查调试日志是否已启用。"""
    return _DEBUG_ENABLED


def get_logger(name: str = "debug") -> logging.Logger:
    """获取可控制的调试 logger，不依赖 configs 配置。"""
    if name in _DEBUG_LOGGERS:
        return _DEBUG_LOGGERS[name]

    logger = logging.getLogger(f"debug_{name}")

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        file_handler = logging.FileHandler(LOGS_PATH / f"{name}.log", encoding="utf-8")

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    if _DEBUG_ENABLED:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.CRITICAL + 1)
        for handler in logger.handlers:
            handler.setLevel(logging.CRITICAL + 1)

    _DEBUG_LOGGERS[name] = logger

    return logger
```

### 19.10 `src/utils/trace.py`

`@trace_span` 装饰器：业务函数级 chain span，自动序列化 args/kwargs 到 Phoenix `INPUT_VALUE`、返回值到 `OUTPUT_VALUE`。tracer 不可用时透明降级。支持 sync / async。

```python
"""@trace_span 装饰器，给编排方法加 Phoenix chain span。

序列化 args/kwargs 到 INPUT_VALUE / 返回值到 OUTPUT_VALUE，支持 Phoenix UI 子串过滤。
tracer 不可用时透明降级，原函数正常执行。
"""
from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from pydantic import BaseModel

from src.utils.log import get_logger

try:
    from openinference.semconv.trace import SpanAttributes

    from src.utils.observe import get_tracer

    TRACING_AVAILABLE = True
except ImportError:
    get_tracer = None  # type: ignore
    SpanAttributes = None  # type: ignore
    TRACING_AVAILABLE = False

logger = get_logger("trace")


def _json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


class TraceSerializer:
    """递归序列化追踪数据。失败降级 str()。"""

    @staticmethod
    def serialize_value(obj: Any) -> Any:
        try:
            try:
                from sqlalchemy.orm import DeclarativeBase
                if isinstance(obj, DeclarativeBase):
                    if hasattr(obj, "to_dict"):
                        return obj.to_dict()
                    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            except Exception:
                pass
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            if isinstance(obj, (list, tuple, set)):
                return [TraceSerializer.serialize_value(x) for x in obj]
            if isinstance(obj, dict):
                return {k: TraceSerializer.serialize_value(v) for k, v in obj.items()}
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            return str(obj)
        except Exception as e:
            logger.debug(f"serialize_value failed {type(obj).__name__}: {e}")
            try:
                return str(obj)
            except Exception:
                return f"<{type(obj).__name__} object - serialization failed>"

    @staticmethod
    def serialize_args_kwargs(args: tuple, kwargs: dict) -> dict:
        try:
            return {
                "args": [TraceSerializer.serialize_value(a) for a in args],
                "kwargs": {k: TraceSerializer.serialize_value(v) for k, v in kwargs.items()},
            }
        except Exception as e:
            logger.warning(f"serialize args/kwargs failed: {e}")
            try:
                return {"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}
            except Exception:
                return {"args": f"<{len(args)} args>", "kwargs": f"<{len(kwargs)} kwargs>"}

    @staticmethod
    def serialize_output(result: Any) -> tuple[str, str]:
        try:
            v = TraceSerializer.serialize_value(result)
            if v is None or isinstance(v, (str, int, float, bool)):
                return _json_dumps({"value": v}), "application/json"
            return _json_dumps(v), "application/json"
        except Exception as e:
            logger.warning(f"serialize_output failed {type(result).__name__}: {e}")
            try:
                return _json_dumps({"trace_output_error": str(e), "raw": str(result)}), "application/json"
            except Exception:
                return _json_dumps({"trace_output_error": str(e)}), "application/json"


@contextmanager
def _trace_context(span_name: str):
    if not TRACING_AVAILABLE:
        yield None, None
        return
    tracer = get_tracer() if get_tracer else None
    if not tracer:
        yield None, None
        return
    span = None
    current = None
    try:
        span = tracer.start_as_current_span(span_name, openinference_span_kind="chain")
        current = span.__enter__()
        yield span, current
    except Exception as e:
        logger.warning(f"create trace span failed {span_name}: {e}")
        yield None, None
    finally:
        if span:
            try:
                span.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"close trace span failed {span_name}: {e}")


def _record_input(current_span, args: tuple, kwargs: dict, span_name: str) -> None:
    if not current_span or not SpanAttributes:
        return
    try:
        data = TraceSerializer.serialize_args_kwargs(args, kwargs)
        current_span.set_attribute(SpanAttributes.INPUT_VALUE, _json_dumps(data))
        current_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
    except Exception as e:
        logger.warning(f"record trace input failed {span_name}: {e}")


def _record_output(current_span, result: Any, span_name: str) -> None:
    if not current_span or not SpanAttributes:
        return
    try:
        s, mime = TraceSerializer.serialize_output(result)
        current_span.set_attribute(SpanAttributes.OUTPUT_VALUE, s)
        current_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, mime)
    except Exception as e:
        logger.warning(f"record trace output failed {span_name}: {e}")


def _record_exception(current_span, exc: Exception, span_name: str) -> None:
    if not current_span:
        return
    try:
        current_span.record_exception(exc)
        current_span.set_attribute("exception.type", type(exc).__name__)
        current_span.set_attribute("exception.message", str(exc))
    except Exception as e:
        logger.warning(f"record exception failed {span_name}: {e}")


def trace_span(span_name: str | None = None):
    """手动 span 装饰器。支持 sync / async。"""

    def decorator(func: Callable):
        _span_name = span_name or getattr(func, "__name__", "unknown")
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with _trace_context(_span_name) as (_span, current):
                    try:
                        _record_input(current, args, kwargs, _span_name)
                        result = await func(*args, **kwargs)
                        _record_output(current, result, _span_name)
                        return result
                    except Exception as e:
                        _record_exception(current, e, _span_name)
                        raise
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with _trace_context(_span_name) as (_span, current):
                try:
                    _record_input(current, args, kwargs, _span_name)
                    result = func(*args, **kwargs)
                    _record_output(current, result, _span_name)
                    return result
                except Exception as e:
                    _record_exception(current, e, _span_name)
                    raise
        return sync_wrapper

    return decorator
```

### 19.11 `src/utils/feishu/`（项目特化，不展开）

飞书 SDK 封装子包，包含：

- `event.py`：飞书事件解析与分发
- `sdk.py`：飞书 OpenAPI 调用包装（`lark-oapi` 适配）
- `ws_client.py`：飞书事件 WebSocket 长连接客户端

代码与项目业务强耦合，模板不展示。具体实现见项目源码 `backend/src/utils/feishu/`。

### 19.12 `src/utils/gateway_client.py`（项目特化，不展开）

内部网关 HTTP 调用客户端封装。代码与项目环境强耦合，模板不展示。具体实现见项目源码 `backend/src/utils/gateway_client.py`。

### 19.13 `src/utils/__init__.py`

留空，按需 re-export 即可。每个 utils 文件独立 import 使用：

```python
from src.utils.log import get_logger
from src.utils.redis import redis_client, init_redis, DistributedLock
from src.utils.time import TimeUtils
from src.utils.trace_id import get_request_id
from src.utils.uuid import get_uuid_without_hyphen
from src.utils.observe import init_phoenix
from src.utils.serializers import MsgSpecJSONResponse
from src.utils.json import json_dumps, parse_json_markdown
from src.utils.trace import trace_span
```

---

## 20. 完整端到端示例：Country 资源

> 以"国家"资源（CRUD 五件套）为例，给出从 Model 到 Controller 的全套**可粘贴运行**代码。新增任意业务模块都按这个骨架翻一遍即可。

### 20.1 Step 1 — Model（`src/models/country.py`）

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Country(Base):
    """国家维度表。"""

    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="国家名称，如 Nigeria")
    code: Mapped[str | None] = mapped_column(String(10), nullable=True, default="", comment="国家代码，如 NG")
    region: Mapped[str | None] = mapped_column(String(50), nullable=True, default="", comment="所属地区部")
    country_size: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None, comment="large / small_medium")
```

注册到 `src/models/__init__.py`（同步更新 import 区和 `__all__` 两处）：

```python
from src.models.base import Base                # 基础模型类
from src.models.country import Country          # 国家信息

__all__ = [
    "Base",        # 基础模型类
    "Country",     # 国家信息
]
```

### 20.2 Step 2 — Schema（`src/schemas/admin.py`）

```python
"""管理类资源的 Pydantic Schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CountryCreate(BaseModel):
    """创建国家请求体。"""
    name: str = Field(..., description="国家名称，如 Nigeria")
    code: str = Field(default="", description="国家代码，如 NG")
    region: str = Field(default="", description="所属地区部，如 West Africa")
    country_size: str | None = Field(default=None, description="large / small_medium / None")


class CountryUpdate(BaseModel):
    """更新国家请求体（不允许改 name）。"""
    code: str | None = None
    region: str | None = None
    country_size: str | None = None


class CountryOut(BaseModel):
    """国家出参视图。"""
    id: str
    name: str
    code: str | None
    region: str | None
    country_size: str | None

    model_config = {"from_attributes": True}
```

### 20.3 Step 3 — CRUD（`src/cruds/country_crud.py`）

```python
"""countries 表 CRUD。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.exception.errors import DBException, ErrorCode
from src.cruds.base_crud import BaseCrud
from src.models.country import Country


class CountryCrud(BaseCrud[Country]):
    model = Country

    def get_by_name(self, session: Session, name: str) -> Country:
        """按 name 查询；找不到抛 ``DBException(NOT_FOUND)``。"""
        row = self.get_by_name_or_none(session, name)
        if row is None:
            raise DBException(f"Country 不存在: name={name}", error_code=ErrorCode.NOT_FOUND)
        return row

    def get_by_name_or_none(self, session: Session, name: str) -> Country | None:
        """按 name 查询；找不到返回 None（用于创建前查重）。"""
        stmt = (
            select(Country)
            .where(Country.name == name)
            .where(Country.delete_flag.is_(False))
        )
        return session.execute(stmt).scalar_one_or_none()

    def list_by_region(self, session: Session, region: str) -> list[Country]:
        """按地区部查询国家列表（按 created_time 倒序）。"""
        stmt = (
            select(Country)
            .where(Country.region == region)
            .where(Country.delete_flag.is_(False))
            .order_by(Country.created_time.desc())
        )
        return list(session.scalars(stmt).all())


country_crud = CountryCrud()
```

继承 `BaseCrud[Country]` 后自动获得：`get_by_id` / `get_by_id_or_none` / `list_all` / `add` / `update` / `soft_delete` / `hard_delete` / `bulk_create` / `bulk_update` / `bulk_soft_delete` / `bulk_hard_delete`。

### 20.4 Step 4 — Service（`src/services/country_service.py`）

```python
"""国家资源业务逻辑。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.common.exception.errors import ErrorCode, ServiceException
from src.cruds.country_crud import country_crud
from src.models.country import Country
from src.schemas.admin import CountryCreate, CountryUpdate


class CountryService:

    def list_all(self, session: Session) -> list[Country]:
        return country_crud.list_all(session)

    def get(self, session: Session, country_id: str) -> Country:
        return country_crud.get_by_id(session, country_id)

    def create(self, session: Session, body: CountryCreate) -> Country:
        # 创建前重名检查：业务上"可能不存在"语义，调 _or_none 版
        existed = country_crud.get_by_name_or_none(session, body.name)
        if existed:
            raise ServiceException(f"国家已存在: {body.name}", error_code=ErrorCode.PARAM_ERROR)
        row = country_crud.add(
            session,
            name=body.name,
            code=body.code,
            region=body.region,
            country_size=body.country_size,
        )
        session.commit()
        session.refresh(row)
        return row

    def update(self, session: Session, country_id: str, body: CountryUpdate) -> Country:
        row = country_crud.update(
            session,
            country_id,
            code=body.code,
            region=body.region,
            country_size=body.country_size,
        )
        session.commit()
        session.refresh(row)
        return row

    def delete(self, session: Session, country_id: str) -> None:
        if country_crud.soft_delete(session, country_id) == 0:
            raise ServiceException(f"国家不存在: {country_id}", error_code=ErrorCode.NOT_FOUND)
        session.commit()


country_service = CountryService()
```

### 20.5 Step 5 — Controller（`src/controllers/api/v1/country.py`）

```python
"""国家资源 RESTful 接口。"""
from __future__ import annotations

from fastapi import APIRouter, Path

from src.common.api_response import api_response
from src.common.response.response_schema import Response
from src.db.session import CurrentSession
from src.models.country import Country
from src.schemas.admin import CountryCreate, CountryOut, CountryUpdate
from src.services.country_service import country_service

router = APIRouter(prefix="/countries", tags=["国家"])


@router.get("", summary="列出所有国家", response_model=Response[list[CountryOut]])
@api_response(list[CountryOut])
def list_countries(session: CurrentSession) -> list[Country]:
    return country_service.list_all(session)


@router.post("", summary="创建国家", response_model=Response[CountryOut])
@api_response(CountryOut)
def create_country(session: CurrentSession, body: CountryCreate) -> Country:
    return country_service.create(session, body)


@router.get("/{country_id}", summary="国家详情", response_model=Response[CountryOut])
@api_response(CountryOut)
def get_country(session: CurrentSession, country_id: str = Path(...)) -> Country:
    return country_service.get(session, country_id)


@router.post("/{country_id}", summary="更新国家", response_model=Response[CountryOut])
@api_response(CountryOut)
def update_country(session: CurrentSession, body: CountryUpdate, country_id: str = Path(...)) -> Country:
    return country_service.update(session, country_id, body)


@router.delete("/{country_id}", summary="软删国家", response_model=Response[None])
@api_response()
def delete_country(session: CurrentSession, country_id: str = Path(...)) -> None:
    country_service.delete(session, country_id)
```

### 20.6 Step 6 — 挂载路由（`src/controllers/api/v1/router.py`）

```python
from fastapi import APIRouter

from src.controllers.api.v1.country import router as country_router

router = APIRouter()
router.include_router(country_router)
# 后续新增资源在此追加 router.include_router(...)
```

### 20.7 Step 7 — 生成迁移并升级数据库

```bash
cd backend

# 自动生成迁移（检测 models 与 DB 差异）
uv run alembic -c src/db/alembic.ini revision --autogenerate -m "add country table"

# 应用迁移（带 Redis 分布式锁，多 Pod 安全）
PYTHONIOENCODING=utf-8 PYTHONPATH=. uv run python scripts/upgrade_db.py
```

### 20.8 Step 8 — 验证

启动 web 进程后访问 `http://localhost:8080/docs` 测试 5 个端点，每个响应都应是统一形态：

```json
{
    "success": true,
    "code": "0",
    "message": "成功",
    "detailMessage": null,
    "data": { "id": "...", "name": "Nigeria", "code": "NG", "region": "West Africa", "country_size": "small_medium" },
    "request_id": "..."
}
```

### 20.9 调用链一图流（数据流）

```
HTTP Request
   ↓
Controller.create_country(body: CountryCreate)
   ├── @api_response(CountryOut) 包装
   └── country_service.create(session, body)
        ├── country_crud.get_by_name_or_none(session, name)                    # 重名检查（_or_none 版）
        ├── country_crud.add(session, **fields)    → ORM Country 实例
        ├── session.commit()                        # service 层显式 commit
        └── return Country
   ↓
@api_response 自动转换：Country → CountryOut.model_validate(row)
   ↓
response_base.success(data=CountryOut)
   ↓
HTTP Response: { success: true, code: "0", data: {...}, request_id: "..." }
```

异常路径：

```
service raise ServiceException("国家已存在", error_code=PARAM_ERROR)
   ↓
@api_response 捕获 AppBaseException → 打日志后 re-raise
   ↓
全局 exception_handler 捕获 AppBaseException
   ↓
渲染：{ success: false, code: "400001", message: "参数错误", detailMessage: "国家已存在: Nigeria", data: null }
```

---

## 21. Worker + Task 骨架示例（业务逻辑剥离）

> 一个 funboost worker 包含三块：**入口函数**（`@boost` 装饰）、**Pydantic 任务模型**（dict ↔ model 边界）、**Processor 类**（业务编排）。下面给出可直接套用的骨架，业务部分用 `# TODO` 注释占位。

### 21.1 Step 1 — 任务模型（`src/schemas/worker_task.py`）

每个队列对应一个 Pydantic 模型，统一在此文件定义：

```python
"""Worker 任务 Schema

每个 funboost 队列对应一个 Pydantic 任务模型。
push 时：task_func.push(XxxTaskData(...).model_dump())
消费时：self.task = XxxTaskData.model_validate(task_data)
"""
from __future__ import annotations

from pydantic import BaseModel


class ExampleTaskData(BaseModel):
    """queue:example — 示例任务输入参数"""
    entity_id: str                    # 主键 / 业务 ID
    action: str = "process"           # 业务动作枚举（按需细化）
    payload: str = ""                 # 透传给 worker 的额外 JSON 串
    # 按需追加业务字段（保持 dict 序列化友好：禁止 datetime / Enum，用 str / int 表示）
```

### 21.2 Step 2 — Worker 文件骨架（`src/worker/example_worker.py`）

```python
"""示例 Worker（funboost @boost）

模板要点：
- 入口函数 @boost 装饰，只接受一个 task: dict
- Processor 类负责业务编排，所有 DB 操作共用一个 session
- 异常向上抛由 funboost 进入重试 / 死信流程
"""
from __future__ import annotations

import logging

from funboost import BoosterParams, boost
from funboost.constant import BrokerEnum, ConcurrentModeEnum
from sqlalchemy.orm import Session

from src.common.redis_keys import RedisKey
from src.configs import configs
from src.db.session import get_db_session
from src.schemas.worker_task import ExampleTaskData
from src.utils.log import get_logger

logger = get_logger("worker.example")

# funboost 队列名手动拼接 prefix（funboost 不会自动注入）
QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_BUSINESS}"


# ── Processor ──────────────────────────────────────────────────────────────
class ExampleProcessor:
    """业务编排器：所有真实业务逻辑放这里，按 step_1 / step_2 / step_3 拆分。"""

    def __init__(self, task_data: dict) -> None:
        # dict → Pydantic（所有字段在此校验，业务代码直接用 self.task.xxx）
        self.task = ExampleTaskData.model_validate(task_data)

    def process(self) -> None:
        """funboost 入口的实际处理方法。

        约束：
        - 一任务一 session：所有 DB 操作必须在同一个 with get_db_session() 块内
        - 末尾 commit；任何异常 rollback 后向上抛，让 funboost 重试 / 死信
        - 内部 step_* 共享同一个 session 与同一个事务
        """
        logger.info(f"[Example] start entity_id={self.task.entity_id} action={self.task.action}")

        # 准入判断（无需 DB 的快过滤先做，省 session）
        if not self.task.entity_id:
            logger.warning("[Example] 缺少 entity_id，直接丢弃")
            return

        with get_db_session() as session:
            try:
                self.step_1_load(session)
                self.step_2_process(session)
                self.step_3_persist(session)
                session.commit()
                logger.info(f"[Example] done entity_id={self.task.entity_id}")
            except Exception as exc:
                session.rollback()
                logger.error(f"[Example] 处理失败 entity_id={self.task.entity_id}: {exc}", exc_info=True)
                raise   # 让 funboost 进入重试 / 死信流程

    def step_1_load(self, session: Session) -> None:
        """加载/校验业务数据。

        - 调用 CRUD 拿主表实体
        - 必要的关联实体一次性加载到 self
        """
        # TODO: 替换为真实业务
        # entity = example_crud.get_by_id(session, self.task.entity_id)
        # self.entity = entity
        ...

    def step_2_process(self, session: Session) -> None:
        """核心业务编排。

        - 第三方 API 调用（飞书 / LLM / 内部网关）放这里
        - 失败时：可重试错误 raise；不可恢复错误转 status 写库后 return
        """
        # TODO: 替换为真实业务
        # result = some_external_sdk.call(self.entity.foo)
        # self.result = result
        ...

    def step_3_persist(self, session: Session) -> None:
        """落库 + 触发下游。

        - 多个 CRUD 写操作组合在同一事务
        - 触发下游 worker：用同模块的 enqueue_task，禁止散字段 push
        """
        # TODO: 替换为真实业务
        # example_crud.update(session, self.task.entity_id, status="DONE")
        # downstream_enqueue_task(DownstreamTaskData(entity_id=self.task.entity_id))
        ...


# ── funboost 入口函数 ───────────────────────────────────────────────────────
@boost(
    BoosterParams(
        queue_name=QUEUE_NAME,
        broker_kind=BrokerEnum.REDIS_STREAM,                  # Redis Stream broker
        concurrent_mode=ConcurrentModeEnum.THREADING,         # 项目固定 THREADING
        qps=configs.MAX_RETRIES,                              # 改为对应 QPS 配置字段
        max_retry_times=configs.MAX_RETRIES,
        logger_name="example_worker",
        log_level=logging.ERROR,
        create_logger_file=False,
        is_push_to_dlx_queue_when_retry_max_times=True,       # 重试耗尽进死信
    )
)
def example_task(task: dict) -> None:
    """funboost consumer 入口：接收 dict，委托 Processor。

    Args:
        task: funboost 推入的 dict，结构同 ExampleTaskData。
    """
    ExampleProcessor(task).process()


# ── 入队 helper（统一入口，禁止业务代码直接调 .push） ─────────────────────────
def enqueue_task(data: ExampleTaskData) -> None:
    """统一入队函数：业务代码调用这里，避免散字段 push。

    Args:
        data: ExampleTaskData 实例；自动 model_dump 后投递到队列。
    """
    example_task.push(data.model_dump())
```

### 21.3 Step 3 — 注册到 worker 进程（`scripts/start_worker.py`）

```python
"""业务 Consumer 进程入口"""
from src.utils.log import init_logger

init_logger("worker", "run_worker.log")
init_logger("worker.example", "run_example_worker.log")  # 按 logger_name 分文件

from funboost import ctrl_c_recv

from src.utils.log import get_logger
from src.utils.redis import init_redis
from src.worker.example_worker import example_task

logger = get_logger("worker")


def main() -> None:
    init_redis()
    logger.info("[Worker] 启动 example_worker consumer ...")
    example_task.consume()
    ctrl_c_recv()


if __name__ == "__main__":
    main()
```

### 21.4 Step 4 — 上游入队示例

任何模块（HTTP controller / 其他 worker / scheduler）需要触发 example 任务时：

```python
# 在 service / scheduler / 其他 worker 中
from src.schemas.worker_task import ExampleTaskData
from src.worker.example_worker import enqueue_task

def some_business_logic():
    # ... 业务处理 ...
    enqueue_task(ExampleTaskData(entity_id="abc123", action="process"))
```

### 21.5 Scanner 模式（定时触发的 Worker）

如果是**定时扫描**场景（如每 30 秒拉一次待处理数据），把上面 Worker 改成 Scanner：

- 文件位置：`src/schedulers/example_scanner.py`
- 入参 task 是空 dict（由 `ApsJobAdder` 定时 push）
- Processor 自己查 DB 找候选并循环处理

```python
"""示例 Scanner（funboost ApsJobAdder 定时触发）"""
from __future__ import annotations

import logging

from funboost import BoosterParams, boost
from funboost.constant import BrokerEnum, ConcurrentModeEnum

from src.common.redis_keys import RedisKey
from src.configs import configs
from src.db.session import get_db_session
from src.utils.log import get_logger

logger = get_logger("scanner.example")

QUEUE_NAME = f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_SCANNER_RECORDING}"


class ExampleScanner:
    """周期性扫描器：每次调度查询候选并串行处理。"""

    def run(self) -> None:
        """执行一轮扫描：查候选 → 逐条处理 → 单条失败不阻塞整批"""
        try:
            with get_db_session() as session:
                # TODO: 查询候选实体
                # candidates = example_crud.list_pending_candidates(session)
                candidates: list = []
        except Exception as exc:
            logger.error(f"[ExampleScanner] 查询候选失败: {exc}", exc_info=True)
            return

        if not candidates:
            return

        logger.info(f"[ExampleScanner] 本次扫描 {len(candidates)} 个候选")
        for entity in candidates:
            try:
                self.process_one(entity)
            except Exception as exc:
                logger.error(f"[ExampleScanner] 处理失败 entity_id={entity.id}: {exc}", exc_info=True)

    def process_one(self, entity) -> None:
        """单条处理：一实体一 session，所有 DB 操作共用一个事务"""
        with get_db_session() as session:
            try:
                # TODO: 真实业务
                # external_data = some_sdk.fetch(entity.id)
                # example_crud.update(session, entity.id, status="DONE")
                session.commit()
            except Exception:
                session.rollback()
                raise


@boost(
    BoosterParams(
        queue_name=QUEUE_NAME,
        broker_kind=BrokerEnum.REDIS_ACK_ABLE,                # scanner 用 ACK_ABLE
        concurrent_mode=ConcurrentModeEnum.THREADING,
        concurrent_num=1,                                     # scanner 单并发，避免重复扫
        max_retry_times=0,
        logger_name="scanner.example",
        log_level=logging.ERROR,
        create_logger_file=False,
        is_push_to_dlx_queue_when_retry_max_times=False,
    )
)
def example_scanner_task(task: dict) -> None:
    """funboost 入口：ApsJobAdder 定时 push 空 dict，触发一轮扫描"""
    ExampleScanner().run()
```

注册定时调度（在 `scripts/start_scheduler.py`）：

```python
from funboost import ApsJobAdder

from src.schedulers.example_scanner import example_scanner_task


def register_schedules() -> None:
    ApsJobAdder(example_scanner_task, job_store_kind="redis").add_push_job(
        trigger="interval",
        seconds=configs.EXAMPLE_SCAN_INTERVAL,
        kwargs={"task": {}},
        id="example_scanner",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
```

### 21.6 Worker / Scanner 选型对照

| 场景 | 选型 | broker_kind | 并发 | 触发方式 |
|------|------|-------------|------|----------|
| 事件驱动（消息到来即处理） | Worker | `REDIS_STREAM` | `THREADING` + N 并发 | 上游 `enqueue_task()` push |
| 定时拉取（每 N 秒扫一次） | Scanner | `REDIS_ACK_ABLE` | `THREADING` + 1 并发 | `ApsJobAdder` 定时 push |
| 长连接事件接入 | 独立进程 | 不走 funboost | 单进程 + Leader 选举 | 进程入口直接拉起 |

### 21.7 funboost 关键约束速查

- ✅ Worker 函数**只接受一个 `task: dict` 参数**
- ✅ 入参 dict 必须由 Pydantic / dataclass `model_dump()` / `asdict()` 得到
- ✅ Processor 第一步 `self.task = XxxTaskData.model_validate(task_data)`，业务代码用 model 字段
- ✅ **一任务一 session**：所有 DB 操作必须在同一个 `with get_db_session()` 块内
- ✅ 异常上抛让 funboost 进入重试 / 死信，**禁止** `try: ... except: pass` 吞异常
- ✅ 队列名 `f"{configs.REDIS_KEY_PREFIX}:{RedisKey.QUEUE_XXX}"` 运行时拼接
- ✅ QPS 来自 `configs.XXX_QPS`，**禁止**硬编码在装饰器里
- ✅ 上游统一调 `enqueue_task(data)` 入队，**禁止**业务代码直接 `task.push(...)`
- ❌ 禁止 `concurrent_mode=ASYNCIO/GEVENT/EVENTLET`，统一 `THREADING`
- ❌ 禁止裸用 `apscheduler.add_job()` 调消费函数本体（多 Pod 重复触发）

---

## 22. 自动化测试

> 测试体系采用**双轨制**：`tests/scripts/` 放数据初始化与诊断脚本（人工触发）；`tests/unit/` 与 `tests/integration/` 放自动化测试用例（CI 自动跑）。

### 22.1 测试目录约定

```
tests/
├── conftest.py                     # 全局 fixture（test engine / client / session）
├── unit/                           # 单元测试：纯函数 + 业务规则验证（可不依赖 DB）
│   ├── test_<service>_service.py
│   └── test_<utility>.py
├── integration/                    # 集成测试：跑真实 MySQL + Redis
│   ├── conftest.py                 # integration 专属 fixture
│   ├── test_<entity>_api.py        # 走 TestClient 的端到端
│   └── test_<entity>_crud.py       # 直接测 CRUD 层
└── scripts/                        # ❶ 现有：数据初始化、诊断、修数（人工跑）
    ├── init_data/
    │   └── seed_<entity>.py
    └── <diagnose_xxx>.py
```

**❶ 已有的 `tests/scripts/`**：保持原职责（数据初始化、诊断、修数），命令行执行 `uv run python -m tests.scripts.init_data.seed_xxx`，**不进 pytest 自动收集**。

### 22.2 关键约束：不要用 SQLite 替代 MySQL

> ⚠️ **禁止**用 `sqlite:///:memory:` 跑测试。MySQL 与 SQLite 在以下方面差异巨大，SQLite 通过的代码到 MySQL 经常翻车：
>
> - SQL 方言（`ON DUPLICATE KEY` / `INSERT IGNORE` 等 MySQL 专用语法 SQLite 不支持）
> - 字符集与排序规则（utf8mb4 vs SQLite 默认）
> - 严格模式行为（SQLite 类型亲和性极宽松）
> - 锁机制与并发行为（InnoDB 行锁 vs SQLite 库级锁）
> - Enum / CHECK 约束 / 索引前缀长度

**用真实 MySQL 8.0 跑测试**，下面给出 docker-compose 方案。

### 22.3 测试环境（docker-compose.test.yml）

放在项目根目录（与 `docker/` 平级）：

```yaml
services:
  mysql-test:
    image: mysql:8.0
    container_name: <project>-mysql-test
    environment:
      MYSQL_ROOT_PASSWORD: rootpw
      MYSQL_DATABASE: <project>_test
      MYSQL_USER: test_user
      MYSQL_PASSWORD: test_secret
    command: >
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_0900_ai_ci
      --default-time-zone='+08:00'
      --sql-mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO'
    ports:
      - "3307:3306"                # 与本机 dev MySQL 错开
    tmpfs:
      - /var/lib/mysql             # 内存盘加速；测试结束自动清空，无需 docker volume

  redis-test:
    image: redis:7-alpine
    container_name: <project>-redis-test
    ports:
      - "6380:6379"                # 与本机 dev Redis 错开
    tmpfs:
      - /data
```

启动测试依赖：

```bash
docker compose -f docker-compose.test.yml up -d
```

### 22.4 全局测试配置（`tests/conftest.py`）

```python
"""全局 pytest fixture。

设计要点：
- session 作用域的 test_engine：一次性建表，全部测试共享 schema
- function 作用域的 db_session：每条用例外层包一个事务，测完整体回滚
  → 用例间天然隔离，不需要清表，速度比 truncate 快得多
- function 作用域的 client：基于 db_session 注入 dependency_overrides
"""
from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


# ── 强制走测试库（避免误连 dev/prod）────────────────────────────────────────
os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3307")
os.environ.setdefault("MYSQL_USER", "test_user")
os.environ.setdefault("MYSQL_PASSWORD", "test_secret")
os.environ.setdefault("MYSQL_DB", "<project>_test")
os.environ.setdefault("REDIS_PORT", "6380")
os.environ.setdefault("REDIS_KEY_PREFIX", "<project>_test")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="db")
def test_engine() -> Generator[Engine, None, None]:
    """整个测试会话共享一个 engine + 完整 schema。"""
    from src.configs import configs
    from src.db.engines import create_sync_engine
    from src.models import Base                       # 确保所有 model 已注册

    engine = create_sync_engine(configs.db_uri, echo=False)
    Base.metadata.drop_all(engine)                    # 防上次残留
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """每条用例独立事务，结束回滚。

    关键：sessionmaker 用 `join_transaction_mode="create_savepoint"`，
    业务代码内部 `session.commit()` 实际是 SAVEPOINT 提交，外层 transaction
    rollback 时整体撤回。这样 service 的 commit 不会污染其他用例。
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",     # SQLAlchemy 2.0 新机制
    )
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient，注入受控的 db_session。"""
    from src.app import app
    from src.db.session import get_db

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> Any:
    """用 fakeredis 替代真实 Redis；不依赖 docker 也能跑单元测试。"""
    import fakeredis

    fake = fakeredis.FakeRedis(decode_responses=False)
    from src.utils import redis as redis_module

    monkeypatch.setattr(redis_module.redis_client, "_client", fake, raising=False)
    monkeypatch.setattr(redis_module.redis_client, "_prefix", "test", raising=False)
    return fake
```

> **依赖**：`fakeredis>=2.20` 加到 `[project.optional-dependencies].test`。

### 22.5 单元测试样例（`tests/unit/test_country_service.py`）

单元测试聚焦**业务规则**，DB 用 in-memory savepoint 模式（仍是真实 MySQL，但走事务回滚），不调外部服务。

```python
"""CountryService 单元测试 — 验证业务规则（重名拒绝、软删等）"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.common.exception.errors import ErrorCode, ServiceException
from src.schemas.admin import CountryCreate
from src.services.country_service import country_service


class TestCountryServiceCreate:
    """create() 业务规则。"""

    def test_create_success(self, db_session: Session) -> None:
        body = CountryCreate(name="Nigeria", code="NG", region="West Africa")
        row = country_service.create(db_session, body)
        assert row.id
        assert row.name == "Nigeria"
        assert row.delete_flag is False

    def test_create_duplicate_name_raises(self, db_session: Session) -> None:
        body = CountryCreate(name="Kenya", code="KE")
        country_service.create(db_session, body)

        with pytest.raises(ServiceException) as exc_info:
            country_service.create(db_session, body)
        assert exc_info.value.error_code == ErrorCode.PARAM_ERROR
        assert "已存在" in exc_info.value.message


class TestCountryServiceDelete:

    def test_soft_delete_marks_flag(self, db_session: Session) -> None:
        row = country_service.create(db_session, CountryCreate(name="Ghana"))
        country_service.delete(db_session, row.id)

        # 软删后 list_all 不再返回
        all_rows = country_service.list_all(db_session)
        assert row.id not in {r.id for r in all_rows}

    def test_delete_nonexistent_raises_not_found(self, db_session: Session) -> None:
        with pytest.raises(ServiceException) as exc_info:
            country_service.delete(db_session, "nonexistent-id")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND
```

### 22.6 集成测试样例（`tests/integration/test_country_api.py`）

集成测试**走 TestClient → 完整 HTTP 链路**，验证 controller / service / crud / response 包装的端到端行为。

```python
"""Country 资源 API 集成测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestCountryAPI:

    def test_create_returns_unified_response(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/countries",
            json={"name": "Nigeria", "code": "NG", "region": "West Africa"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # 统一响应形态校验
        assert body["success"] is True
        assert body["code"] == "0"
        assert body["data"]["name"] == "Nigeria"
        assert "request_id" in body

    def test_create_duplicate_returns_business_error(self, client: TestClient) -> None:
        client.post("/api/v1/countries", json={"name": "Kenya"})
        resp = client.post("/api/v1/countries", json={"name": "Kenya"})
        # 业务异常仍返回 200，body 里 success=false
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "400001"          # PARAM_ERROR

    def test_get_nonexistent_returns_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/countries/nonexistent-id")
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "400005"          # NOT_FOUND

    def test_validation_error_returns_422_code(self, client: TestClient) -> None:
        resp = client.post("/api/v1/countries", json={})  # 缺 name
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "400002"          # VALIDATION_ERROR
```

### 22.7 Worker 测试样例（`tests/integration/test_example_worker.py`）

不启动 funboost consumer，直接构造 task dict 跑 `Processor.process()`：

```python
"""Worker Processor 集成测试 — 跳过队列，直测业务编排。"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.schemas.worker_task import ExampleTaskData
from src.worker.example_worker import ExampleProcessor


class TestExampleProcessor:

    def test_process_happy_path(self, db_session: Session, fake_redis) -> None:
        # 1. 准备前置数据
        # entity = entity_crud.add(db_session, ...)
        # db_session.flush()

        # 2. 构造任务 dict（与上游 enqueue 一致）
        task_data = ExampleTaskData(entity_id="abc123", action="process").model_dump()

        # 3. 直接跑 Processor，不经队列
        processor = ExampleProcessor(task_data)
        # processor 内部会自己 with get_db_session()，
        # 所以这个测试主要验证它能跑通；细粒度断言走 service 单测更合适
        processor.process()

        # 4. 断言副作用（DB 状态变化、redis 写入等）
        # ...

    def test_process_invalid_task_raises(self) -> None:
        with pytest.raises(Exception):
            ExampleProcessor({"bad": "data"})    # 缺 entity_id，Pydantic 抛错
```

### 22.8 pytest 命令速查

```bash
# 启动测试依赖
docker compose -f docker-compose.test.yml up -d

# 跑全部
uv run pytest

# 只跑单元测试（不依赖 docker）
uv run pytest tests/unit/

# 只跑集成测试
uv run pytest tests/integration/

# 跑特定标记
uv run pytest -m integration         # 见 §1.1 markers
uv run pytest -m "not slow"

# 覆盖率（需打开 pyproject 里的 --cov 选项）
uv run pytest --cov=src --cov-report=html

# 只跑某个文件 / 类 / 方法
uv run pytest tests/unit/test_country_service.py
uv run pytest tests/unit/test_country_service.py::TestCountryServiceCreate
uv run pytest tests/unit/test_country_service.py::TestCountryServiceCreate::test_create_success
```

### 22.9 测试规范要点

- ✅ **一个测试只断言一件事**：失败时一眼看出哪个规则被破坏
- ✅ **测试类组织相关用例**：`TestCountryServiceCreate` / `TestCountryServiceDelete`
- ✅ **断言业务异常的 `error_code`**：不只是 `pytest.raises(ServiceException)`
- ✅ **集成测试用 `client` fixture**：单元测试用 `db_session` fixture
- ✅ **fake_redis 优先**：能用 fakeredis 就不要起真实 Redis（CI 启动更快）
- ❌ 禁止测试间共享状态（用 fixture 隔离）
- ❌ 禁止把 `tests/scripts/` 里的脚本写成 pytest 用例（职责不同）

---

## 23. MySQL 8.0 生产环境七大坑

> 同步 SQLAlchemy + MySQL 8.0 在生产经常踩到的问题集合。每条都给出**根因 + 对策代码**。

### 23.1 `MySQL server has gone away`（错误码 2006/2013）

**根因**：
- 连接被 MySQL `wait_timeout` 主动断开（云数据库默认 60-600 秒，比本地 28800 短得多）
- 网络瞬断 / 中间件（HAProxy / 阿里云 SLB）超时回收
- `max_allowed_packet` 太小，发了大 BLOB 被踢

**对策**：本模板的 §6.2 `engines.py` 已经覆盖：
- `pool_pre_ping=True` — 取连接前先 ping，断了就重建
- `pool_recycle=3600` — 主动回收，必须**小于** MySQL `wait_timeout`
- 大字段写入：联系 DBA 调大 `max_allowed_packet`（默认 64MB）

```bash
# 排查云数据库的 wait_timeout
mysql> SHOW VARIABLES LIKE 'wait_timeout';
# 如果是 60，本地 pool_recycle 必须改成 < 60，比如 30
```

### 23.2 死锁 `Deadlock found when trying to get lock`（错误码 1213 / 1205）

**根因**：MySQL 比 PG 更容易死锁，常见场景：
- 并发更新同一行
- 并发 INSERT 命中相同唯一索引
- 不同事务以**不同顺序**锁多行

InnoDB 自动选一个事务回滚，**应用层必须捕获并重试**：

```python
# src/utils/retry.py
import logging
from functools import wraps
from typing import Any, Callable

from sqlalchemy.exc import OperationalError

from src.utils.log import get_logger

logger = get_logger("retry")

# MySQL 错误码：1213=死锁，1205=锁等待超时
_RETRYABLE_MYSQL_CODES = (1213, 1205)


def retry_on_deadlock(max_attempts: int = 3, wait_seconds: float = 0.1) -> Callable:
    """死锁自动重试装饰器。仅用于幂等操作（DDL / 业务幂等的 update）。"""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except OperationalError as exc:
                    if not exc.orig or exc.orig.args[0] not in _RETRYABLE_MYSQL_CODES:
                        raise
                    if attempt == max_attempts:
                        logger.exception(f"[retry_on_deadlock] {fn.__qualname__} 重试耗尽")
                        raise
                    logger.warning(f"[retry_on_deadlock] {fn.__qualname__} attempt={attempt}, sleeping {wait_seconds}s")
                    time.sleep(wait_seconds * attempt)
            return None
        return wrapper
    return decorator
```

用法：

```python
from src.utils.retry import retry_on_deadlock

class CountryService:

    @retry_on_deadlock(max_attempts=3)
    def update_critical(self, session, country_id, body):
        ...
```

> **注意**：死锁重试的前提是**事务幂等**。非幂等操作（比如 INSERT 后再 UPDATE）必须先抽取成幂等才能重试。

### 23.3 自增 ID 跳号

**根因**：MySQL 8.0 默认 `innodb_autoinc_lock_mode=2`（交错模式），事务回滚 / 服务重启会跳号。这是设计如此，不是 bug。

**对策**：本项目主键已统一用 **UUID hex**（见 §6.4），天然无此问题。如果业务上有自增字段（比如订单流水号），**绝对不要把自增 ID 作为对外业务编号**——单独建一张 sequence 表，或用 Redis `INCR`。

### 23.4 `utf8mb4` 与索引长度

**根因**：MySQL 8.0 单字符 4 字节，B-Tree 索引单列上限 3072 字节，所以 `VARCHAR(768)` 就是单列索引的常见上限。

**对策**：
- 唯一索引字段 `String(255)` 是安全值
- 超长字段（如长 URL）建唯一索引时，加哈希列 `url_hash: String(64) UNIQUE` 索引哈希
- `Text` 字段不要直接建索引，建前缀索引：`Index("ix_xxx_content", "content", mysql_length=200)`

### 23.5 大偏移分页性能塌陷

**根因**：`OFFSET 100000 LIMIT 20` 要扫前 10 万行后丢弃，深分页性能爆炸。

**对策**：换**游标分页**（基于 `(created_time, id)` 复合键）：

```python
# ❌ offset 分页：page=5000 时慢得令人发指
def list_paginated(session, page: int, page_size: int):
    return session.scalars(
        select(Todo)
        .order_by(Todo.created_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

# ✅ 游标分页：性能与 offset 无关，只与 page_size 相关
def list_after(session, last_created_time: datetime | None, last_id: str | None, page_size: int = 20):
    stmt = select(Todo).where(Todo.delete_flag.is_(False))
    if last_created_time and last_id:
        stmt = stmt.where(
            (Todo.created_time, Todo.id) < (last_created_time, last_id)
        )
    stmt = stmt.order_by(Todo.created_time.desc(), Todo.id.desc()).limit(page_size)
    return list(session.scalars(stmt).all())
```

**前端兼容性**：游标分页适合"加载更多"列表（移动端、瀑布流），不适合"跳转到第 N 页"的传统分页。如果业务必须支持跳转，offset 分页+索引覆盖也能撑到 10 万级；超过 10 万必须切游标分页。

### 23.6 连接池容量公式

多进程 + 多 Pod 部署下，DB 连接池容易爆 MySQL `max_connections`。

**公式**：

```
总连接数 = Pod 数 × (web 进程 + worker 进程 + scheduler 进程) × (POOL_SIZE + POOL_MAX_OVERFLOW)
       ≤ MySQL max_connections × 0.8
```

举例：
- 3 个 Pod × 3 个进程（web/worker/scheduler）= 9 个 SQLAlchemy engine
- 每个 engine `POOL_SIZE=50` + `POOL_MAX_OVERFLOW=50` = 100
- 总连接 = 9 × 100 = **900**
- MySQL `max_connections` 必须 ≥ 1125（留 20% 余量给 DBA / 监控 / 临时连接）

**排查命令**：

```sql
-- 当前最大连接数
SHOW VARIABLES LIKE 'max_connections';

-- 当前应用占用
SELECT user, host, COUNT(*) FROM information_schema.processlist GROUP BY user, host;

-- 历史峰值
SHOW STATUS LIKE 'Max_used_connections';
```

**对策**：
- 应用层：scheduler 进程的 `POOL_SIZE` 调小到 5-10（它本来访问 DB 就少）
- DB 层：DBA 调大 `max_connections`（但 InnoDB 每连接消耗 ~256KB 内存，要预留）

### 23.7 Starlette 线程池

**根因**：FastAPI 同步路由（`def`）在 Starlette 默认 ~40 大小的线程池里执行。请求量大时线程不够用，新请求排队。

**对策**：调大线程池 + 同步扩大连接池（否则"线程拿到了但抢不到连接"）：

```python
# scripts/start_web.py
import anyio
import uvicorn

from src.configs import configs


def main() -> None:
    if configs.UVICORN_WORKER_NUM != 1:
        raise RuntimeError("...")

    # 调大默认线程池（默认约 40）
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = configs.STARLETTE_THREAD_POOL_SIZE  # 100-200 都常见

    uvicorn.run("src.app:app", host="0.0.0.0", port=int(...), workers=1)
```

**调整原则**：
- 线程池大小 ≤ `POOL_SIZE + POOL_MAX_OVERFLOW`，否则空抢连接
- 线程池过大会占用大量内存（每线程 ~8MB 栈）
- 实测：纯 CRUD 服务 100 通常够用；调用大量外部 HTTP 的服务可以加到 200

---

## 24. 性能与可观测性

### 24.1 慢查询日志

生产开启慢查询日志，定位偶发慢 SQL：

```sql
-- 查看当前配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 调整（DBA 操作；云数据库通常控制台能改）
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.5;          -- 慢于 500ms 的 SQL 都记
```

定期用 [`pt-query-digest`](https://docs.percona.com/percona-toolkit/pt-query-digest.html) 分析慢日志：

```bash
pt-query-digest /var/log/mysql/slow.log > slow_report.txt
```

### 24.2 EXPLAIN 检查索引

高频查询提交前必须 EXPLAIN 确认走索引：

```sql
EXPLAIN FORMAT=JSON
SELECT * FROM countries
WHERE region = 'West Africa' AND delete_flag = 0
ORDER BY created_time DESC
LIMIT 20;
```

关注点：
- `access_type`：`ref` / `range` 可接受；`ALL`（全表扫）必须优化
- `rows`：扫描行数；与结果集行数差距过大说明索引选择性不够
- `Extra: Using filesort` / `Using temporary`：查询会排序 / 用临时表，看是否能加复合索引消除

### 24.3 连接池监控

应用层暴露连接池指标，及早发现连接泄漏：

```python
# src/controllers/system/health.py
from fastapi import APIRouter

from src.common.api_response import api_response
from src.common.response.response_schema import Response
from src.db.engines import sync_engine

router = APIRouter()


@router.get("/system/db_pool", summary="DB 连接池状态")
@api_response()
def db_pool_status() -> dict:
    pool = sync_engine.pool
    return {
        "size": pool.size(),                    # 池大小
        "checked_in": pool.checkedin(),         # 空闲连接
        "checked_out": pool.checkedout(),       # 借出连接
        "overflow": pool.overflow(),            # 溢出连接数
    }
```

或者接 Prometheus / Grafana：

```python
# 暴露成 metrics
from prometheus_client import Gauge

db_pool_checked_out = Gauge("db_pool_checked_out", "DB connections currently checked out")
db_pool_overflow = Gauge("db_pool_overflow", "DB connections in overflow")

# 周期性更新（背景线程或定时任务）
def update_metrics():
    pool = sync_engine.pool
    db_pool_checked_out.set(pool.checkedout())
    db_pool_overflow.set(pool.overflow())
```

**告警阈值参考**：
- `checked_out / (size + overflow) > 0.8` 持续 1 分钟 → 连接池吃紧
- `overflow > 0` 持续出现 → `POOL_SIZE` 配小了，需要调大

### 24.4 应用层耗时中间件

记录每个请求的耗时，配合 `X-Request-ID` 串联：

```python
# src/middleware/request_logging_middleware.py（在 §9.2 基础上扩展）
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.log import get_logger

logger = get_logger("api_access", filename="api_access.log")
_SKIP_PATHS = {"/health", "/actuator/health/readiness", "/actuator/health/liveness"}

# 慢请求阈值（毫秒）
SLOW_REQUEST_THRESHOLD_MS = 1000


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 注入响应头方便前端 / 网关采集
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

        # 慢请求单独 warn 级别
        log_fn = logger.warning if elapsed_ms > SLOW_REQUEST_THRESHOLD_MS else logger.info
        log_fn(f"{request.method} {request.url.path} {response.status_code} {elapsed_ms:.1f}ms")
        return response
```

### 24.5 SQL 计数中间件（开发期排查 N+1）

开发环境可选打开，统计每个请求触发了多少条 SQL：

```python
# src/middleware/sql_count_middleware.py
import threading
from contextlib import contextmanager

from sqlalchemy import event
from starlette.middleware.base import BaseHTTPMiddleware

from src.db.engines import sync_engine
from src.utils.log import get_logger

logger = get_logger("sql_count")

_local = threading.local()


@event.listens_for(sync_engine, "before_cursor_execute")
def _before_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    if hasattr(_local, "count"):
        _local.count += 1


class SqlCountMiddleware(BaseHTTPMiddleware):
    """开发期统计每个请求的 SQL 数量，排查 N+1。仅 dev 环境启用。"""

    async def dispatch(self, request, call_next):
        _local.count = 0
        response = await call_next(request)
        sql_count = getattr(_local, "count", 0)
        if sql_count > 20:                       # N+1 嫌疑阈值
            logger.warning(f"[N+1?] {request.method} {request.url.path} 触发 {sql_count} 条 SQL")
        response.headers["X-SQL-Count"] = str(sql_count)
        return response
```

`app.py` 里按环境注册：

```python
if configs.ENVIRONMENT == "dev":
    app.add_middleware(SqlCountMiddleware)
```

---

> **本文档版本**：v3.0
> **维护原则**：项目规范变更时同步更新本文档；新项目套用前请按"§17 落地检查表"逐项核对。
> **v3.0 变更**：参见文档头"v3 增量"摘要。

# 子计划 1：基础设施 + 后端骨架 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 executing-plans 逐任务实现。步骤用 `- [ ]` 勾选跟踪。每个代码步骤先写失败测试、看它失败、再写最小实现、看它通过、提交（TDD）。

**Goal:** 搭起可运行的后端骨架与本地基础设施——`docker compose up` 后 `/api/health` 返回 `{"status":"ok"}`，pytest 全绿。

**Architecture:** FastAPI(异步) + Controller–Service–Repository 分层骨架；Postgres/Redis/MinIO 由 docker-compose 编排；alembic 管迁移（基线启用 pg_trgm）。本计划只搭骨架与基础设施，不含业务表与业务逻辑（留给子计划 2+）。

**Tech Stack:** Python 3.12、FastAPI、uvicorn、SQLAlchemy 2.0(async)+asyncpg、Alembic、arq、Redis、MinIO、pytest+pytest-asyncio+httpx。

**Definition of Done:** ①`pytest` 全绿；②`docker compose config` 通过；③`docker compose up -d` 后 `curl localhost:8000/api/health` 返回 ok；④目录分层与 spec 第 12 节一致。

---

## 文件结构（本计划产出）

```
api/
  requirements.txt          # 依赖
  pyproject.toml            # pytest 配置
  Dockerfile               # api/worker 共用镜像
  alembic.ini              # alembic 配置
  app/
    __init__.py
    main.py                # FastAPI 装配
    core/__init__.py  core/config.py     # pydantic-settings
    db/__init__.py    db/base.py  db/session.py
    controllers/__init__.py  controllers/health.py
    worker/__init__.py  worker/settings.py   # arq 占位（空任务集）
  migrations/
    env.py  script.py.mako  versions/0001_baseline.py
  tests/
    __init__.py  conftest.py  test_config.py  test_health.py
docker-compose.yml          # postgres/redis/minio/minio-init/api/worker
.env.example
README.md
```

---

### Task 1：依赖与 pytest 配置

**Files:**
- Create: `api/requirements.txt`
- Create: `api/pyproject.toml`
- Create: `api/app/__init__.py`（空）
- Create: `api/tests/__init__.py`（空）

- [ ] **Step 1：写依赖文件 `api/requirements.txt`**

```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.7
pydantic-settings>=2.3
sqlalchemy[asyncio]>=2.0.30
asyncpg>=0.29
alembic>=1.13
psycopg2-binary>=2.9         # 仅 alembic 迁移用同步驱动
arq>=0.26
redis>=5.0
minio>=7.2
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7
pypdf>=4.2
httpx>=0.27
python-multipart>=0.0.9
pytest>=8.2
pytest-asyncio>=0.23
```

- [ ] **Step 2：写 `api/pyproject.toml`（pytest 异步自动模式）**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3：建空包文件**

`api/app/__init__.py` 与 `api/tests/__init__.py` 写入单行注释 `# package`。

- [ ] **Step 4：安装依赖并验证 pytest 可用**

Run: `cd api && pip install -r requirements.txt && pytest -q`
Expected: `no tests ran`（目前无测试）——证明 pytest 已就绪。

- [ ] **Step 5：提交**（git 由用户在 Windows 侧执行，下同；命令供参考）

```bash
git add api/requirements.txt api/pyproject.toml api/app/__init__.py api/tests/__init__.py
git commit -m "chore: api deps and pytest config"
```

---

### Task 2：配置层 `core/config.py`（TDD）

**Files:**
- Create: `api/app/core/__init__.py`（空）
- Create: `api/app/core/config.py`
- Test: `api/tests/test_config.py`

- [ ] **Step 1：写失败测试 `api/tests/test_config.py`**

```python
from app.core.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.redis_url.startswith("redis://")
    assert s.minio_bucket_sources == "sources"
    assert s.jwt_expire_min == 720
    # 异步驱动校验：DATABASE_URL 必须走 asyncpg
    assert "+asyncpg" in s.database_url
```

- [ ] **Step 2：运行测试，确认失败**

Run: `cd api && pytest tests/test_config.py -q`
Expected: FAIL（`ModuleNotFoundError: app.core.config`）

- [ ] **Step 3：写最小实现 `api/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB / 队列
    database_url: str = "postgresql+asyncpg://llmwiki:llmwiki@postgres:5432/llmwiki"
    redis_url: str = "redis://redis:6379/0"
    arq_max_tries: int = 3
    arq_job_timeout: int = 900

    # Auth
    jwt_secret: str = "change-me-in-prod"
    jwt_expire_min: int = 720

    # 对象存储
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_sources: str = "sources"
    minio_bucket_assets: str = "assets"
    minio_secure: bool = False

    # LLM（仅生成）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    app_url: str = "http://localhost"


settings = Settings()
```

- [ ] **Step 4：运行测试，确认通过**

Run: `cd api && pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add api/app/core/__init__.py api/app/core/config.py api/tests/test_config.py
git commit -m "feat: settings via pydantic-settings"
```

---

### Task 3：DB 引擎与 Session（无需实连）

**Files:**
- Create: `api/app/db/__init__.py`（空）
- Create: `api/app/db/base.py`
- Create: `api/app/db/session.py`
- Test: `api/tests/test_db_wiring.py`

- [ ] **Step 1：写失败测试 `api/tests/test_db_wiring.py`**

```python
from app.db.base import Base
from app.db.session import SessionLocal, engine


def test_db_objects_wired():
    # 不实连数据库，只验证对象装配正确
    assert Base.metadata is not None
    assert engine is not None
    assert SessionLocal.kw["expire_on_commit"] is False
```

- [ ] **Step 2：运行测试，确认失败**

Run: `cd api && pytest tests/test_db_wiring.py -q`
Expected: FAIL（`ModuleNotFoundError: app.db.base`）

- [ ] **Step 3：写实现**

`api/app/db/base.py`:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`api/app/db/session.py`:
```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4：运行测试，确认通过**

Run: `cd api && pytest tests/test_db_wiring.py -q`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add api/app/db/
git commit -m "feat: async sqlalchemy engine and session"
```

---

### Task 4：FastAPI 应用 + 健康检查（TDD，端到端）

**Files:**
- Create: `api/app/controllers/__init__.py`（空）
- Create: `api/app/controllers/health.py`
- Create: `api/app/main.py`
- Create: `api/tests/conftest.py`
- Test: `api/tests/test_health.py`

- [ ] **Step 1：写失败测试 `api/tests/test_health.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2：运行测试，确认失败**

Run: `cd api && pytest tests/test_health.py -q`
Expected: FAIL（`ModuleNotFoundError: app.main`）

- [ ] **Step 3：写实现**

`api/app/controllers/health.py`:
```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

`api/app/main.py`:
```python
from fastapi import FastAPI

from app.controllers import health


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Wiki API")
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
```

`api/tests/conftest.py`（占位，后续计划放共享 fixtures）:
```python
# shared pytest fixtures live here in later plans
```

- [ ] **Step 4：运行测试，确认通过**

Run: `cd api && pytest tests/test_health.py -q`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add api/app/main.py api/app/controllers/ api/tests/conftest.py api/tests/test_health.py
git commit -m "feat: fastapi app with health endpoint"
```

---

### Task 5：arq worker 占位

**Files:**
- Create: `api/app/worker/__init__.py`（空）
- Create: `api/app/worker/settings.py`
- Test: `api/tests/test_worker_settings.py`

- [ ] **Step 1：写失败测试 `api/tests/test_worker_settings.py`**

```python
from app.worker.settings import WorkerSettings


def test_worker_settings_has_redis_and_functions():
    assert hasattr(WorkerSettings, "functions")
    assert isinstance(WorkerSettings.functions, list)  # 子计划3会注册 ingest_source
    assert WorkerSettings.redis_settings is not None
```

- [ ] **Step 2：运行测试，确认失败**

Run: `cd api && pytest tests/test_worker_settings.py -q`
Expected: FAIL（`ModuleNotFoundError: app.worker.settings`）

- [ ] **Step 3：写实现 `api/app/worker/settings.py`**

```python
from arq.connections import RedisSettings

from app.core.config import settings


class WorkerSettings:
    # 子计划3 会把 ingest_source 加入 functions
    functions: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = settings.arq_max_tries
    job_timeout = settings.arq_job_timeout
```

- [ ] **Step 4：运行测试，确认通过**

Run: `cd api && pytest tests/test_worker_settings.py -q`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add api/app/worker/
git commit -m "feat: arq worker settings placeholder"
```

---

### Task 6：Alembic 初始化 + 基线迁移（启用 pg_trgm）

**Files:**
- Create: `api/alembic.ini`
- Create: `api/migrations/env.py`
- Create: `api/migrations/script.py.mako`
- Create: `api/migrations/versions/0001_baseline.py`

- [ ] **Step 1：写 `api/alembic.ini`（最小）**

```ini
[alembic]
script_location = migrations
[loggers]
keys = root
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 2：写 `api/migrations/env.py`（用同步驱动跑迁移）**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

config = context.config
# 把 asyncpg 异步 URL 换成同步驱动给 alembic 用
sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 3：写 `api/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4：写基线迁移 `api/migrations/versions/0001_baseline.py`**

```python
"""baseline: enable pg_trgm

Revision ID: 0001_baseline
Revises:
"""
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

- [ ] **Step 5：验证迁移脚本可被 alembic 识别**

Run: `cd api && alembic history`
Expected: 列出 `0001_baseline`（无报错即通过；实际 `alembic upgrade head` 在 Task 7 容器内连库执行）

- [ ] **Step 6：提交**

```bash
git add api/alembic.ini api/migrations/
git commit -m "feat: alembic baseline with pg_trgm"
```

---

### Task 7：Dockerfile + docker-compose + .env.example（基础设施）

**Files:**
- Create: `api/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1：写 `api/Dockerfile`（api 与 worker 共用）**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2：写 `.env.example`**

```
DATABASE_URL=postgresql+asyncpg://llmwiki:llmwiki@postgres:5432/llmwiki
REDIS_URL=redis://redis:6379/0
JWT_SECRET=change-me-in-prod
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_SOURCES=sources
MINIO_BUCKET_ASSETS=assets
MINIO_SECURE=false
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
APP_URL=http://localhost
```

- [ ] **Step 3：写 `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: llmwiki
      POSTGRES_PASSWORD: llmwiki
      POSTGRES_DB: llmwiki
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U llmwiki"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: ["miniodata:/data"]

  minio-init:
    image: minio/mc
    depends_on: [minio]
    entrypoint: >
      /bin/sh -c "
      until (mc alias set local http://minio:9000 minioadmin minioadmin) do sleep 2; done;
      mc mb -p local/sources local/assets;
      exit 0;"

  api:
    build: ./api
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_started}
      minio: {condition: service_started}
    command: >
      /bin/sh -c "alembic upgrade head &&
      uvicorn app.main:app --host 0.0.0.0 --port 8000"
    ports: ["8000:8000"]

  worker:
    build: ./api
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_started}
    command: ["arq", "app.worker.settings.WorkerSettings"]

volumes:
  pgdata:
  miniodata:
```

- [ ] **Step 4：验证 compose 文件合法**

Run: `docker compose config -q`
Expected: 无输出、退出码 0（语法合法）

- [ ] **Step 5：端到端起服务并验证健康检查**

Run: `cp .env.example .env && docker compose up -d --build && sleep 20 && curl -s localhost:8000/api/health`
Expected: `{"status":"ok"}`；`docker compose logs api` 中可见 `alembic upgrade head` 成功、监听 8000。

- [ ] **Step 6：提交**

```bash
git add api/Dockerfile docker-compose.yml .env.example
git commit -m "feat: docker-compose infra (postgres/redis/minio) + api/worker"
```

---

### Task 8：README 快速开始

**Files:**
- Create: `README.md`

- [ ] **Step 1：写 `README.md`（最小可跑通说明）**

````markdown
# 企业 LLM-Wiki（MVP）

基于 Karpathy 的 LLM-Wiki 模式的企业知识库。详见 `docs/superpowers/specs/`。

## 本地启动
```bash
cp .env.example .env   # 按需填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
docker compose up -d --build
curl localhost:8000/api/health   # -> {"status":"ok"}
```

## 后端测试
```bash
cd api && pip install -r requirements.txt && pytest -q
```
````

- [ ] **Step 2：提交**

```bash
git add README.md
git commit -m "docs: readme quickstart"
```

---

## Self-Review（计划自检）

- **Spec 覆盖**：本计划覆盖 spec 第 3（技术栈）、第 4（部署拓扑）、第 12（分层骨架）。业务表/逻辑/前端不在本计划范围（子计划 2-5）。✓
- **占位符扫描**：无 TODO/TBD；每个代码步骤含完整代码。✓
- **类型一致**：`WorkerSettings.functions: list`、`Settings` 字段名与子计划 2+ 引用保持一致；`settings.database_url` 含 `+asyncpg`，alembic 内替换为 `+psycopg2`。✓
- **依赖顺序**：Task 2(config)→3(db)→4(app)→5(worker)→6(alembic)→7(compose) 单向无环。✓

## 执行交接

计划已存 `docs/superpowers/plans/2026-06-13-mvp-plan-01-infra-skeleton.md`。两种执行方式：
1. **子代理驱动（推荐）**：每个 Task 派一个子代理实现 + 两阶段评审（先合规、再质量），我在任务间审查。
2. **本会话内逐批执行**：直接在当前会话按 Task 顺序实现，带检查点。

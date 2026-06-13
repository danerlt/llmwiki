# 企业 LLM-Wiki MVP — 设计文档（Spec）

> 状态：待用户 review（第 4 版）· 日期：2026-06-13 · 方法论：superpowers
> 本文档经用户确认后进入 `writing-plans`，再按 TDD 实现。

> **版本记录**
> - v2：移除 pgvector/embedding/chunks（回归 LLM-Wiki 反 RAG 本意）；Python 3.12。
> - v3：摄入改用 **Redis + arq**（轻量异步任务队列）替代 BackgroundTasks，新增独立 **worker** 容器——参考 Dify 的 api/worker 分离，任务持久化、可重试、容器重启不丢。
> - v4：后端重构为 **Controller–Service–Repository 分层（MVC）**，明确依赖方向与各层职责（见第 12 节）。

---

## 1. 目标与背景

基于 Karpathy 的 LLM-Wiki 模式，为企业搭建"会自我维护的知识库"。核心区别于 RAG：**LLM 把知识增量编译成带交叉引用的结构化 wiki 页面**，查询时**沿结构导航**（看 index 目录、跟 `[[wikilink]]`、关键词定位），而非每次对原始 chunk 做向量召回重推。本期交付一个**单机 docker-compose 跑通**的 MVP，验证核心闭环 + 四级权限隔离。

**核心闭环**：上传源 →（入队 Redis）→ worker 跑确定性摄入管线（两步 LLM）→ 生成带溯源的 wiki 页（含 index 目录与 wikilink）→ 权限感知的"关键词+图导航"检索问答。

**为什么不用向量/RAG**：知识已被编译成结构化页面，检索靠目录与链接导航即可；引入 embedding 只会徒增 embedding 模型、向量维度、chunks 表等复杂度，既偏离原思想，也违背"架构尽量简单"。

## 2. 范围

### 2.1 MVP 功能（8 项）

1. **账号登录** — JWT，角色 `user` / `admin`；单组织；用户由 admin 创建（含 seed 脚本初始化 admin + 样例组织架构）。
2. **组织结构** — 部门（多级树）、团队（跨部门显式成员）、用户（归属单一部门）。
3. **知识库（KB）命名空间** — 四类作用域：`company`（1 个）/ `department`（每部门 1 个）/ `team`（每团队 1 个）/ `personal`（每人 1 个）。每个 KB 有一个 `index` 目录页（自动维护）。
4. **源上传与解析** — 支持 MD / TXT / PDF（PDF 仅文本层，OCR 不在 MVP）。文件存 MinIO。
5. **确定性摄入管线（异步 worker）** — 入队 → 解析 → 两步 LLM（分析→生成）→ 生成 wiki 页（带 `sources[]` 溯源 + `[[wikilink]]`）→ 解析链接写入图、更新 index 目录、刷新全文检索索引。
6. **Wiki 浏览** — 按 KB 列页、看详情、markdown 渲染、wikilink 可点击跳转。
7. **权限感知检索问答** — 关键词检索 + wikilink/源图扩展 + index 目录，**严格按调用者可见 KB 过滤**，返回带引用的回答。
8. **关键词搜索** — 跨可见 KB 的搜索框（Postgres 全文 / trgm）。

### 2.2 非目标（明确推迟到 V2+）

向量/embedding 语义检索（逃生舱，非 LLM-Wiki 路线）、知识图谱可视化、Deep Research/联网、浏览器扩展、Lint 健康检查、**个人→公司晋升流水线**、Review 审核队列、SSO/SCIM、派生知识"污点传播"撤权、docx/pptx/xlsx 多格式、OCR、Milvus、部门 curator 委派、多组织/多租户。

## 3. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | **Python 3.12** + FastAPI | 异步；uvicorn |
| ORM/迁移 | SQLAlchemy 2.0 (async) + Alembic | |
| 数据库 | PostgreSQL 16 + **pg_trgm**（+ 内置全文检索） | 元数据 + 关键词检索；**不装 pgvector** |
| 任务队列 | **Redis + arq** | 轻量 asyncio 原生任务队列（类 Celery 但更轻），契合异步栈；参考 Dify 的 api/worker 分离；任务持久、可重试、容器重启不丢 |
| 对象存储 | **MinIO**（S3 兼容） | 原始源文件、抽取图片；`StorageBackend` 抽象，未来可换 OSS/S3 |
| 前端 | React 18 + Vite + TypeScript + Tailwind + react-markdown | SPA，nginx 托管构建产物 |
| LLM | OpenAI 兼容接口（默认） | `base_url`+`key`+`model` 注入；兼容 DeepSeek/通义/Kimi/OpenAI；**仅用于生成，无 embedding** |
| 测试 | pytest + httpx AsyncClient | LLMClient 依赖注入便于 mock |
| 编排 | docker-compose（单机） | postgres / redis / minio / api / worker / web / minio-init |

**简化决策**：不引入 Milvus/pgvector（不做向量）。检索以 **Postgres 全文/trgm 关键词检索为基础召回**，叠加 **wikilink + 共享源的图扩展** 与 **index 目录页**。引入 **Redis 仅为摄入任务的持久化队列**（有意识地用一个组件换取任务可靠性）。中文分词用 trgm 子串匹配兜底，zhparser 列为 V2。

## 4. 部署拓扑（docker-compose 单机，api/worker 分离）

```
┌──────────────────────────── docker-compose (单台服务器) ────────────────────────────┐
│  ┌──────────┐   ┌──────────┐                                                        │
│  │  web     │   │  api     │── 入队 ──┐                                              │
│  │ nginx +  │──▶│ FastAPI  │         ▼                                              │
│  │ React    │   │ :8000    │     ┌────────┐      ┌──────────┐                       │
│  │ :80      │◀──│          │◀────▶│ redis  │◀────▶│ worker   │ (arq)                 │
│  └──────────┘   └────┬─────┘ 取状态└────────┘ 消费 │ 跑摄入管线│                       │
│                      │                            └────┬─────┘                       │
│            ┌─────────┴───────────┐                     │                              │
│            ▼                     ▼                     ▼                              │
│      ┌─────────────┐      ┌──────────────────┐   (生成调用 LLM、写库、写 MinIO)        │
│      │ postgres    │      │ minio :9000       │                                       │
│      │ pg_trgm+FTS │      │ sources/assets    │◀── minio-init(建桶)                   │
│      └─────────────┘      └──────────────────┘                                       │
└──────────────────────┼───────────────────────────────────────────────────────────────┘
                       ▼  外部 LLM（OpenAI 兼容，可配；仅文本生成）
```

`api` 与 `worker` 跑同一份代码镜像、不同启动命令（api=uvicorn，worker=arq）。生产部署 = 这台服务器 `docker compose up -d`。

## 5. 数据模型（PostgreSQL）

```
users(id uuid pk, email unique, password_hash, display_name,
      role enum[user,admin], department_id fk→departments null, created_at)

departments(id uuid pk, name, parent_id fk→departments null, created_at)   -- 多级树，祖先用 recursive CTE

teams(id uuid pk, name, created_at)
user_teams(user_id fk, team_id fk, pk(user_id,team_id))                    -- 跨部门成员

knowledge_bases(id uuid pk, scope_type enum[company,department,team,personal],
      scope_ref_id uuid null, name, created_at, unique(scope_type, scope_ref_id))

sources(id uuid pk, kb_id fk, uploader_id fk, filename, content_type,
      storage_key, status enum[pending,processing,done,failed], error null,
      job_id text null, created_at)            -- job_id=arq 任务 id，便于查状态/重试

wiki_pages(id uuid pk, kb_id fk, title, slug, page_type enum[index,source_summary,entity,concept,overview],
      content_md text, frontmatter jsonb, source_ids uuid[],
      search_tsv tsvector,                       -- 全文检索列(GIN 索引)；另对 content_md 建 gin_trgm
      created_at, updated_at, unique(kb_id, slug))

page_links(from_page_id fk→wiki_pages, to_slug text, to_page_id fk→wiki_pages null,
      pk(from_page_id, to_slug))                 -- 解析 [[wikilink]] 得到；to_page_id 命中时回填
```

> **无 `chunks`、无 `embedding`、无 pgvector。** 检索直接作用于 `wiki_pages`，关联靠 `page_links` 与 `source_ids` 重叠。

## 6. 权限模型（核心，不能省）

### 6.1 读权限 — 可见 KB 集合

```
accessible_kb_ids(user) =
    { company KB }
  ∪ { 用户所在部门 及其所有祖先部门 的 department KB }   # recursive CTE 向上 walk parent_id
  ∪ { 用户加入的每个团队 的 team KB }
  ∪ { 用户自己的 personal KB }
```

语义：在"后端组"的人能看"技术部""公司"的 wiki，但**看不到平级"前端组"**；团队是跨部门的独立成员集合。

### 6.2 写权限（MVP 粗粒度）

| KB 作用域 | 谁可写 |
|---|---|
| personal | 本人（kb.scope_ref_id == user.id）|
| team | 团队成员 |
| department | `admin` |
| company | `admin` |

部门级 curator 委派 = V2。

### 6.3 不可逾越的铁律

**所有检索/问答/搜索结果，进入 LLM 上下文或返回前端之前，必须先按 `accessible_kb_ids(user)` 过滤。** 严禁"全量召回 + prompt 提示模型别说"。MVP 第一天就要测到位（专门的权限不变量测试）。

## 7. 对象存储布局（MinIO）

- Bucket `sources`：`{kb_id}/{source_id}/{filename}` — 原始上传文件（不可变）。
- Bucket `assets`：`{kb_id}/{source_id}/{n}.png` — 抽取图片（MVP 可暂不产出）。
- Postgres 仅存 `storage_key`，不存二进制。
- 抽象接口 `StorageBackend`（`put/get/presigned_url`），实现类 `MinioStorage`。

## 8. 摄入管线（确定性，两步，异步 worker）

```
POST /sources（上传）
  → 存 MinIO，建 sources 行 status=pending
  → arq.enqueue_job("ingest_source", source_id) 入队 Redis，回写 sources.job_id
  → 立即返回 { source_id, status:pending }

worker（arq）消费 ingest_source(source_id)：
     1. status=processing
     2. 取文件 → 解析纯文本（MD/TXT 直读；PDF 用 pypdf 提取文本层）
     3. Step1 分析(LLM) → 结构化 JSON
        { entities[], concepts[], key_claims[], links_to_existing[], contradictions[] }
     4. Step2 生成(LLM)：分析 + 该 KB 现有 index 目录 → 产出 wiki 页(markdown)
        - 必含 1 个 source_summary 页（兜底：LLM 漏了用模板补）
        - entity / concept 页，frontmatter 含 sources:[source_id], type, title
        - 用 [[wikilink]] 交叉引用
     5. upsert wiki_pages(按 kb_id+slug)，写 source_ids 溯源
     6. 解析每页 [[wikilink]] → 写 page_links（命中既有页回填 to_page_id）
     7. 重建该 KB 的 index 目录页（按 page_type 分组列出所有页）
     8. 刷新 search_tsv 全文检索列
     9. status=done（异常 → status=failed + error）
```

**可靠性**：arq 任务持久在 Redis；worker/api 重启不丢；失败按 `max_tries`（默认 3）自动重试，仍失败则置 `failed` 落库。**护栏**：page_type 受约束枚举；每页强制 `sources[]`；Step1 输出走 JSON schema 校验，失败重试 1 次再降级兜底。**幂等**：同 source 重跑按 kb_id+slug upsert，不产生重复页。

## 9. 检索与问答（关键词 + 图导航 + 目录，无向量）

```
POST /query { question, kb_scope? }
  1. kbs = accessible_kb_ids(user)（可选与 kb_scope 求交）
  2. 关键词召回：Postgres 全文检索(search_tsv) + trgm 相似，WHERE kb_id IN kbs，标题命中加权 → 种子页
  3. 图扩展：从种子页沿 page_links（直接链接）与 source_ids 重叠（共享源）拉入相关页（nashsu 4 信号精简版）
  4. 始终附上各相关 KB 的 index 目录页，给 LLM 一张"地图"
  5. 预算控制：按页/字数上限截断，保留高分页全文
  6. 组装上下文：编号引用每页（标题 + page_id）
  7. LLM 生成答案，要求用 [1][2] 引用
  8. 返回 { answer, citations:[{page_id,title,kb_id}] }
```

`GET /search?q=&kb=` 走第 2 步返回页列表（不调生成 LLM）。

## 10. API 端点（FastAPI）

```
POST /api/auth/login            → {access_token}
GET  /api/me                    → 当前用户 + 可见 KB 概要
# 组织（admin）
GET/POST /api/departments       GET/POST /api/teams   POST /api/teams/{id}/members   POST /api/users
# KB / 源 / Wiki
GET  /api/kbs                            → 我可见的 KB
GET/POST /api/kbs/{id}/sources           （POST=上传，入队摄入）
GET  /api/sources/{id}                   → 状态/错误（轮询 job 进度）
GET  /api/kbs/{id}/pages   GET /api/pages/{id}
# 检索
GET  /api/search?q=&kb=     POST /api/query     GET /api/health
```

所有非 auth 端点经 JWT 依赖 + 权限校验（读写按第 6 节）。

## 11. 配置（环境变量）

```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://redis:6379/0           # arq broker
ARQ_MAX_TRIES=3   ARQ_JOB_TIMEOUT=900    # 摄入超时 15min
JWT_SECRET=...           JWT_EXPIRE_MIN=720
MINIO_ENDPOINT=minio:9000  MINIO_ACCESS_KEY=  MINIO_SECRET_KEY=
MINIO_BUCKET_SOURCES=sources  MINIO_BUCKET_ASSETS=assets  MINIO_SECURE=false
LLM_BASE_URL=  LLM_API_KEY=  LLM_MODEL=          # 仅文本生成
APP_URL=http://localhost
```

`.env.example` 提供完整样例。**无 EMBEDDING_* 配置。**

## 12. 项目结构（分层 / MVC）

### 12.1 分层与依赖规则

- **Controller（控制器）** `controllers/`：HTTP 入口，**薄**；只做参数校验、调 service、返回 schema。不写业务逻辑、不碰 DB。
- **Service（业务逻辑）** `services/`：编排业务规则与事务；调 repository 取数、调 integrations 访问外部依赖。
- **Repository（数据访问）** `repositories/`：封装**所有** SQLAlchemy 查询；其它层不得直接写 DB 查询。
- **Model（模型）** `models/`：SQLAlchemy ORM。
- **Schema（视图/DTO）** `schemas/`：Pydantic 请求/响应模型（API 的 "View" = 序列化边界）。
- **铁规则**：依赖单向 `controllers → services → repositories → models`；schemas 在边界；**禁止跨层/反向依赖**（controller 不直接碰 repository/DB）。
- MVC 映射：**M** = models + repositories，**V** = schemas，**C** = controllers；service 层承载业务逻辑，使 controller 保持轻薄。

### 12.2 目录树

```
E:\ai\llmwiki\
  docker-compose.yml   .env.example   README.md
  docs/superpowers/{specs,plans}/
  api/
    pyproject.toml  requirements.txt  alembic.ini  Dockerfile
    app/
      main.py                     # 应用装配：路由注册、中间件、异常处理、生命周期
      core/
        config.py                 # pydantic-settings 读取环境变量
        security.py               # 密码哈希 + JWT 编解码
        deps.py                   # 通用依赖：get_db / get_current_user / require_admin
        exceptions.py             # 业务异常 + 统一 handler
        logging.py
      db/
        base.py                   # Declarative Base + metadata
        session.py                # async engine / async_sessionmaker
      models/                     # M：ORM
        user.py department.py team.py knowledge_base.py source.py wiki_page.py page_link.py
      schemas/                    # V：Pydantic DTO
        auth.py org.py kb.py source.py wiki.py query.py common.py
      repositories/               # 数据访问层（DAO）——唯一写 ORM 查询的地方
        base.py user_repo.py org_repo.py kb_repo.py source_repo.py wiki_repo.py
      services/                   # 业务逻辑层
        auth_service.py org_service.py kb_service.py
        permission_service.py     # accessible_kb_ids / can_write —— 核心、重点测试
        ingest_service.py         # 摄入编排（被 worker 调用）
        retrieval_service.py      # 关键词 + 图扩展 + 目录
      controllers/                # C：HTTP 控制器（APIRouter，薄）
        auth.py org.py kb.py sources.py wiki.py query.py health.py
      integrations/               # 外部依赖封装（便于 mock）
        llm.py                    # LLMClient（OpenAI 兼容，仅生成）
        storage.py                # StorageBackend + MinioStorage
      ingest/
        parser.py                 # 文件 → 纯文本（MD/TXT/PDF）
        pipeline.py               # 两步管线步骤（被 ingest_service 编排）
      worker/
        settings.py               # arq WorkerSettings
        tasks.py                  # ingest_source 任务（薄，调 ingest_service）
        queue.py                  # arq 连接 + enqueue 封装
    migrations/                   # alembic versions
    tests/
      conftest.py
      test_permissions.py test_ingest.py test_retrieval.py test_api_auth.py test_api_flow.py
  web/
    package.json vite.config.ts Dockerfile nginx.conf
    src/{api,pages,components,App.tsx,main.tsx}
  scripts/seed.py                 # 初始化 admin + 样例部门/团队/用户/KB
```

> api 与 worker 共用 `api/` 镜像：api 启 `uvicorn app.main:app`，worker 启 `arq app.worker.settings.WorkerSettings`。

## 13. 测试策略（TDD）

- **铁律**：先写失败测试，看它失败，再写最小实现（RED-GREEN-REFACTOR）。
- **重点对象 `services/permission_service.py`**：真实 DB 构造部门树、跨部门团队、个人 KB，断言隔离正确（下级不串平级、机密不外泄）。
- **摄入编排 `services/ingest_service.py`**：直接 `await ingest_service.ingest_source(...)`（绕过 arq，测纯逻辑），mock `LLMClient` 与 `StorageBackend`（依赖注入），断言生成页带正确 `source_ids`、兜底 summary、page_type 受限、page_links 正确、幂等。
- **队列**：轻量集成测试——enqueue 后断言 sources.job_id 写入、状态流转（用 fakeredis 或测试 redis）。
- **检索**：断言结果**永远不含**不可见 KB 的页（权限不变量）；断言图扩展能拉到直接链接页。
- **API**：httpx AsyncClient 端到端（登录→上传→轮询 done→查询）。
- 测试 DB：docker postgres，事务回滚隔离用例。
- 前端：Vitest 覆盖关键组件即可，重心在后端正确性。

## 14. 已确认决策 & 未决（请 review）

**已采纳默认**：检索=关键词+wikilink 图+目录（**不用向量/RAG**）；摄入=**Redis + arq 异步 worker**（持久、可重试，api/worker 分离，参考 Dify）；中文检索 trgm+全文（不上 zhparser）；用户由 admin 创建+seed（不自助注册）；Python 3.12；git 由用户在 Windows 侧自行管理。

**仍请确认**：除上述外是否还有其他设计点要调整？无则进入 `writing-plans`。

## 15. 下一步

本文档经你 review 通过 → 调用 `writing-plans` 产出**逐任务、含完整代码与测试、2–5 分钟粒度**的实现计划（存 `docs/superpowers/plans/`）→ 按 TDD 用子代理逐任务实现。

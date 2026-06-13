# 子计划 3：源上传 + 确定性摄入管线 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 executing-plans 逐任务实现。步骤用 `- [ ]` 勾选跟踪。每个代码步骤先写失败测试、看它失败、再写最小实现、看它通过、提交（TDD）。

**Goal:** 实现"上传源文件 → 入队 → worker 跑两步 LLM 摄入管线 → 生成带溯源(`source_ids`)与 `[[wikilink]]` 的 wiki 页 → 写链接图 → 重建 index 目录页"的确定性闭环，并用 TDD 锁死核心不变量（每页带 `sources[]`、page_type 受限枚举、漏 summary 自动兜底、幂等 upsert、链接解析）。

**Architecture:** Controller–Service–Repository 分层。摄入编排集中在 `services/ingest_service.py`，对外部依赖 `LLMClient` / `StorageBackend` 用**依赖注入**便于 mock。worker 的 `tasks.ingest_source` 仅装配真实依赖并调用 service（薄）。两步 LLM 均以 **JSON 契约**输出，pipeline 做健壮解析 + 降级兜底，保证确定性可测。

**Tech Stack:** FastAPI(UploadFile)、SQLAlchemy 2.0(async)、arq、minio、pypdf、httpx(LLM 调用)、pytest+aiosqlite。

**Definition of Done:**
- ①`pytest` 全绿（含摄入不变量用例：source_ids 正确、兜底 summary、page_type 受限、page_links 解析、幂等）；
- ②上传端点 `POST /api/kbs/{kb_id}/sources` 经 `can_write` 鉴权，存储 + 建 `sources` 行 pending + 入队 + 回写 `job_id`，返回 `{source_id, status:"pending"}`；
- ③`alembic` 链为 `0001 → 0002 → 0003`（迁移用 `alembic revision` 生成骨架后填正文）；
- ④`ingest_source(session, source_id, llm=, storage=)` 可绕过 arq 直接 await 测试。

**测试基础设施决策:** 沿用子计划 2 的 `sqlite+aiosqlite:///:memory:`（`tests/conftest.py` 的 `session`/`client` 夹具）。`frontmatter` 与 `source_ids` 用 SQLAlchemy `JSON`（SQLite/Postgres 均可移植）。Postgres 专属的 `tsvector`/`gin_trgm` 全文检索列**不在本计划**，留给子计划 4（检索）；本计划只产出页与链接图。`LLMClient`/`StorageBackend` 测试中用内存 Fake，不连真 LLM/MinIO/Redis。

---

## 文件结构（本计划产出/修改）

```
api/
  requirements.txt                      # 修改：确认 minio/pypdf/httpx 已在（已在则免改）
  app/
    models/
      source.py wiki_page.py page_link.py     # 新增
      __init__.py                              # 修改：注册新模型
    integrations/
      __init__.py storage.py llm.py            # 新增：StorageBackend+MinioStorage / LLMClient
    ingest/
      __init__.py parser.py pipeline.py        # 新增：文件→文本 / 两步管线
    repositories/
      source_repo.py wiki_repo.py              # 新增
    services/
      ingest_service.py                        # 新增：摄入编排（crown jewel）
    schemas/source.py                          # 新增
    controllers/sources.py                     # 新增
    worker/
      queue.py                                 # 新增：arq 连接 + enqueue 封装
      tasks.py                                 # 新增：ingest_source 任务（薄）
      settings.py                              # 修改：functions=[ingest_source]
    main.py                                    # 修改：注册 sources 路由
  migrations/versions/<rev>_sources_wiki_pages_page_links.py  # 新增（alembic revision 生成）
  tests/
    test_ingest_models.py test_source_repo.py test_wiki_repo.py
    test_parser.py test_pipeline.py test_ingest_service.py
    test_api_sources.py                        # 新增
    fakes.py                                   # 新增：FakeLLM / FakeStorage 共享夹具
```

> 测试统一命令（本机 uv venv）：`cd api && .venv/Scripts/python.exe -m pytest <路径> -q`

---

### Task 1：ORM 模型 source / wiki_page / page_link

**Files:**
- Create: `api/app/models/source.py` `api/app/models/wiki_page.py` `api/app/models/page_link.py`
- Modify: `api/app/models/__init__.py`
- Test: `api/tests/test_ingest_models.py`

- [ ] **Step 1：写失败测试 `tests/test_ingest_models.py`**

```python
import uuid

from app.models import KnowledgeBase, PageLink, Source, User, WikiPage
from app.models.wiki_page import PAGE_TYPES


async def test_source_and_page_persist(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    session.add(kb)
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add(u)
    await session.flush()

    src = Source(
        kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k", status="pending",
    )
    session.add(src)
    await session.flush()
    assert src.status == "pending" and src.error is None

    page = WikiPage(
        kb_id=kb.id, title="实体A", slug="实体A", page_type="entity",
        content_md="# 实体A\n见 [[概念B]]", frontmatter={"type": "entity"},
        source_ids=[str(src.id)],
    )
    session.add(page)
    await session.flush()
    assert page.source_ids == [str(src.id)]
    assert "entity" in PAGE_TYPES

    link = PageLink(from_page_id=page.id, to_slug="概念B", to_page_id=None)
    session.add(link)
    await session.flush()
    assert link.to_page_id is None
```

- [ ] **Step 2：运行测试，确认失败**

Run: `cd api && .venv/Scripts/python.exe -m pytest tests/test_ingest_models.py -q`
Expected: FAIL（`ImportError: cannot import name 'Source'`）

- [ ] **Step 3：建模型文件**

`app/models/source.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SOURCE_STATUSES = ("pending", "processing", "done", "failed")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("knowledge_bases.id"))
    uploader_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`app/models/wiki_page.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

PAGE_TYPES = ("index", "source_summary", "entity", "concept", "overview")


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (UniqueConstraint("kb_id", "slug", name="uq_wiki_kb_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("knowledge_bases.id"))
    title: Mapped[str] = mapped_column(String(512))
    slug: Mapped[str] = mapped_column(String(512))
    page_type: Mapped[str] = mapped_column(String(32))
    content_md: Mapped[str] = mapped_column(Text, default="")
    frontmatter: Mapped[dict] = mapped_column(JSON, default=dict)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`app/models/page_link.py`:
```python
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PageLink(Base):
    __tablename__ = "page_links"

    from_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wiki_pages.id"), primary_key=True
    )
    to_slug: Mapped[str] = mapped_column(String(512), primary_key=True)
    to_page_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wiki_pages.id"), nullable=True
    )
```

- [ ] **Step 4：改 `app/models/__init__.py` 注册新模型**

```python
from app.models.department import Department
from app.models.knowledge_base import KnowledgeBase
from app.models.page_link import PageLink
from app.models.source import Source
from app.models.team import Team, UserTeam
from app.models.user import User
from app.models.wiki_page import WikiPage

__all__ = [
    "Department",
    "KnowledgeBase",
    "PageLink",
    "Source",
    "Team",
    "UserTeam",
    "User",
    "WikiPage",
]
```

- [ ] **Step 5：运行测试，确认通过**

Run: `cd api && .venv/Scripts/python.exe -m pytest tests/test_ingest_models.py -q`
Expected: PASS

- [ ] **Step 6：提交**

```bash
git add api/app/models/source.py api/app/models/wiki_page.py api/app/models/page_link.py api/app/models/__init__.py api/tests/test_ingest_models.py
git commit -m "feat(models): sources/wiki_pages/page_links ORM 模型（JSON 溯源 + page_type 枚举）"
```

---

### Task 2：迁移 0003（sources + wiki_pages + page_links）

> **CLAUDE.md 硬性规则：迁移文件必须用 `alembic revision` 生成骨架，再编辑 upgrade/downgrade 正文。不得手写整文件。**

**Files:**
- Create（由命令生成）: `api/migrations/versions/<rev>_sources_wiki_pages_page_links.py`

- [ ] **Step 1：生成迁移骨架**

Run: `cd api && .venv/Scripts/python.exe -m alembic revision -m "sources wiki_pages page_links"`
Expected: 生成 `migrations/versions/<hash>_sources_wiki_pages_page_links.py`，其中 `down_revision = "0002_org_kb"`（alembic 自动取当前 head）。

- [ ] **Step 2：填 `upgrade()` / `downgrade()` 正文**（只编辑生成文件的函数体，保留顶部 revision/down_revision）

```python
def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("job_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sources_kb_id", "sources", ["kb_id"])
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("slug", sa.String(512), nullable=False),
        sa.Column("page_type", sa.String(32), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("frontmatter", sa.JSON(), nullable=True),
        sa.Column("source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("kb_id", "slug", name="uq_wiki_kb_slug"),
    )
    op.create_index("ix_wiki_pages_kb_id", "wiki_pages", ["kb_id"])
    op.create_table(
        "page_links",
        sa.Column("from_page_id", sa.Uuid(), sa.ForeignKey("wiki_pages.id"), primary_key=True),
        sa.Column("to_slug", sa.String(512), primary_key=True),
        sa.Column("to_page_id", sa.Uuid(), sa.ForeignKey("wiki_pages.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("page_links")
    op.drop_index("ix_wiki_pages_kb_id", "wiki_pages")
    op.drop_table("wiki_pages")
    op.drop_index("ix_sources_kb_id", "sources")
    op.drop_table("sources")
```

- [ ] **Step 3：验证迁移链可被识别**

Run: `cd api && .venv/Scripts/python.exe -m alembic history`
Expected: 列出 `0001_baseline -> 0002_org_kb -> <rev> (head)`，无报错。

- [ ] **Step 4：提交**

```bash
git add api/migrations/versions/
git commit -m "feat(db): 迁移 0003 建 sources/wiki_pages/page_links 表"
```

---

### Task 3：Fake 依赖 + 源仓储 source_repo

**Files:**
- Create: `api/tests/fakes.py`、`api/app/repositories/source_repo.py`
- Test: `api/tests/test_source_repo.py`

- [ ] **Step 1：写共享 Fake `tests/fakes.py`**（后续 Task 6/7/9 复用）

```python
"""测试用内存 Fake：不连真 LLM / MinIO。"""


class FakeStorage:
    """内存对象存储，实现 StorageBackend 接口。"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return f"memory://{key}"


class FakeLLM:
    """按调用顺序返回预设响应；记录收到的 prompt 便于断言。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._responses.pop(0) if self._responses else ""
```

- [ ] **Step 2：写失败测试 `tests/test_source_repo.py`**

```python
import uuid

from app.models import KnowledgeBase, User
from app.repositories import source_repo


async def _kb_user(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add_all([kb, u])
    await session.flush()
    return kb, u


async def test_create_get_and_status_flow(session):
    kb, u = await _kb_user(session)
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k",
    )
    await session.flush()
    assert src.status == "pending"

    got = await source_repo.get_by_id(session, src.id)
    assert got is not None and got.id == src.id

    await source_repo.set_job_id(session, src.id, "job-1")
    await source_repo.set_status(session, src.id, "failed", error="boom")
    await session.flush()
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.job_id == "job-1"
    assert refreshed.status == "failed" and refreshed.error == "boom"


async def test_list_by_kb(session):
    kb, u = await _kb_user(session)
    await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k1",
    )
    await session.flush()
    rows = await source_repo.list_by_kb(session, kb.id)
    assert len(rows) == 1
```

- [ ] **Step 3：运行测试，确认失败** —— `ImportError: cannot import name 'source_repo'`。

- [ ] **Step 4：实现 `app/repositories/source_repo.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source


async def create(
    session: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploader_id: uuid.UUID,
    filename: str,
    content_type: str,
    storage_key: str,
    status: str = "pending",
) -> Source:
    src = Source(
        kb_id=kb_id,
        uploader_id=uploader_id,
        filename=filename,
        content_type=content_type,
        storage_key=storage_key,
        status=status,
    )
    session.add(src)
    return src


async def get_by_id(session: AsyncSession, source_id: uuid.UUID) -> Source | None:
    res = await session.execute(select(Source).where(Source.id == source_id))
    return res.scalar_one_or_none()


async def set_status(
    session: AsyncSession, source_id: uuid.UUID, status: str, error: str | None = None
) -> None:
    src = await get_by_id(session, source_id)
    if src is not None:
        src.status = status
        src.error = error


async def set_job_id(session: AsyncSession, source_id: uuid.UUID, job_id: str) -> None:
    src = await get_by_id(session, source_id)
    if src is not None:
        src.job_id = job_id


async def list_by_kb(session: AsyncSession, kb_id: uuid.UUID) -> list[Source]:
    res = await session.execute(select(Source).where(Source.kb_id == kb_id))
    return list(res.scalars().all())
```

- [ ] **Step 5：运行测试，确认通过**；**Step 6：提交**

```bash
git add api/tests/fakes.py api/app/repositories/source_repo.py api/tests/test_source_repo.py
git commit -m "feat(repo): source_repo（创建/取/状态流转/列表）+ 测试 Fake"
```

---

### Task 4：Wiki 仓储 wiki_repo（upsert + 链接图）

**Files:**
- Create: `api/app/repositories/wiki_repo.py`
- Test: `api/tests/test_wiki_repo.py`

- [ ] **Step 1：写失败测试 `tests/test_wiki_repo.py`**

```python
from app.models import KnowledgeBase
from app.repositories import wiki_repo


async def _kb(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    session.add(kb)
    await session.flush()
    return kb


async def test_upsert_is_idempotent_by_kb_slug(session):
    kb = await _kb(session)
    p1 = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="v1", frontmatter={}, source_ids=["s1"],
    )
    await session.flush()
    p2 = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="v2", frontmatter={}, source_ids=["s1", "s2"],
    )
    await session.flush()
    assert p1.id == p2.id  # 同 kb+slug 复用同一行
    assert p2.content_md == "v2" and p2.source_ids == ["s1", "s2"]
    assert len(await wiki_repo.list_by_kb(session, kb.id)) == 1


async def test_replace_links_and_backfill(session):
    kb = await _kb(session)
    a = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="见 [[概念B]]", frontmatter={}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["概念B"])
    await session.flush()
    # 概念B 还不存在 → to_page_id 为空
    links = await wiki_repo.links_from(session, a.id)
    assert links[0].to_slug == "概念B" and links[0].to_page_id is None

    b = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="概念B", title="概念B",
        page_type="concept", content_md="x", frontmatter={}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    links = await wiki_repo.links_from(session, a.id)
    assert links[0].to_page_id == b.id  # 回填命中
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/repositories/wiki_repo.py`**

```python
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PageLink, WikiPage


async def get_by_slug(session: AsyncSession, kb_id: uuid.UUID, slug: str) -> WikiPage | None:
    res = await session.execute(
        select(WikiPage).where(WikiPage.kb_id == kb_id, WikiPage.slug == slug)
    )
    return res.scalar_one_or_none()


async def get_by_id(session: AsyncSession, page_id: uuid.UUID) -> WikiPage | None:
    res = await session.execute(select(WikiPage).where(WikiPage.id == page_id))
    return res.scalar_one_or_none()


async def list_by_kb(session: AsyncSession, kb_id: uuid.UUID) -> list[WikiPage]:
    res = await session.execute(select(WikiPage).where(WikiPage.kb_id == kb_id))
    return list(res.scalars().all())


async def upsert(
    session: AsyncSession,
    *,
    kb_id: uuid.UUID,
    slug: str,
    title: str,
    page_type: str,
    content_md: str,
    frontmatter: dict,
    source_ids: list[str],
) -> WikiPage:
    page = await get_by_slug(session, kb_id, slug)
    if page is None:
        page = WikiPage(kb_id=kb_id, slug=slug)
        session.add(page)
    page.title = title
    page.page_type = page_type
    page.content_md = content_md
    page.frontmatter = frontmatter
    page.source_ids = source_ids
    return page


async def replace_links(
    session: AsyncSession, *, from_page_id: uuid.UUID, to_slugs: list[str]
) -> None:
    await session.execute(delete(PageLink).where(PageLink.from_page_id == from_page_id))
    for slug in dict.fromkeys(to_slugs):  # 去重保序
        session.add(PageLink(from_page_id=from_page_id, to_slug=slug, to_page_id=None))


async def links_from(session: AsyncSession, from_page_id: uuid.UUID) -> list[PageLink]:
    res = await session.execute(
        select(PageLink).where(PageLink.from_page_id == from_page_id)
    )
    return list(res.scalars().all())


async def backfill_link_targets(session: AsyncSession, *, kb_id: uuid.UUID) -> None:
    """把本 KB 内 to_slug 命中既有页 slug 的 page_links 回填 to_page_id。"""
    pages = await list_by_kb(session, kb_id)
    slug_to_id = {p.slug: p.id for p in pages}
    page_ids = list(slug_to_id.values())
    if not page_ids:
        return
    res = await session.execute(
        select(PageLink).where(PageLink.from_page_id.in_(page_ids))
    )
    for link in res.scalars().all():
        link.to_page_id = slug_to_id.get(link.to_slug)
```

- [ ] **Step 4：运行测试，确认通过**；**Step 5：提交**

```bash
git add api/app/repositories/wiki_repo.py api/tests/test_wiki_repo.py
git commit -m "feat(repo): wiki_repo（按 kb+slug 幂等 upsert、链接 replace/backfill）"
```

---

### Task 5：集成层 integrations（StorageBackend + LLMClient）

**Files:**
- Create: `api/app/integrations/__init__.py`（`# package`）、`api/app/integrations/storage.py`、`api/app/integrations/llm.py`
- Test: `api/tests/test_integrations_contract.py`

> 真实 MinIO/HTTP 调用不做单测（集成期手测），本任务只测**接口契约**：Fake 与真实类签名一致、`LLMClient` 装配不报错。

- [ ] **Step 1：写失败测试 `tests/test_integrations_contract.py`**

```python
from app.integrations.llm import LLMClient
from app.integrations.storage import MinioStorage, StorageBackend
from tests.fakes import FakeStorage


def test_fake_storage_satisfies_protocol():
    s: StorageBackend = FakeStorage()
    s.put("k", b"hi", "text/plain")
    assert s.get("k") == b"hi"
    assert s.presigned_url("k").startswith("memory://")


def test_minio_storage_constructs_without_connecting():
    # 仅构造，不发起网络请求
    store = MinioStorage(
        endpoint="minio:9000", access_key="x", secret_key="y",
        bucket="sources", secure=False,
    )
    assert store.bucket == "sources"


def test_llm_client_constructs():
    c = LLMClient(base_url="http://llm", api_key="k", model="m")
    assert c.model == "m"
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/integrations/storage.py`**

```python
from typing import Protocol, runtime_checkable

from minio import Minio


@runtime_checkable
class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def presigned_url(self, key: str, expires: int = 3600) -> str: ...


class MinioStorage:
    """S3 兼容对象存储（MinIO）。键形如 {kb_id}/{source_id}/{filename}。"""

    def __init__(
        self, *, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool
    ) -> None:
        self.bucket = bucket
        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        import io

        self._client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        from datetime import timedelta

        return self._client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires)
        )
```

- [ ] **Step 4：实现 `app/integrations/llm.py`**

```python
import httpx


class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端（仅文本生成，无 embedding）。"""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
```

> 注：`LLMClient.__init__` 用关键字参数；测试里 `LLMClient(base_url=..., api_key=..., model=...)`。

- [ ] **Step 5：运行测试，确认通过**；**Step 6：提交**

```bash
git add api/app/integrations/ api/tests/test_integrations_contract.py
git commit -m "feat(integrations): StorageBackend+MinioStorage、OpenAI 兼容 LLMClient"
```

---

### Task 6：解析器 parser + 两步管线 pipeline

**Files:**
- Create: `api/app/ingest/__init__.py`（`# package`）、`api/app/ingest/parser.py`、`api/app/ingest/pipeline.py`
- Test: `api/tests/test_parser.py`、`api/tests/test_pipeline.py`

- [ ] **Step 1：写失败测试 `tests/test_parser.py`**

```python
from app.ingest.parser import parse_to_text, slugify


def test_parse_markdown_and_txt():
    assert parse_to_text("a.md", "text/markdown", "# 标题\n正文".encode()) == "# 标题\n正文"
    assert parse_to_text("a.txt", "text/plain", b"hello") == "hello"


def test_parse_unknown_falls_back_to_utf8():
    assert parse_to_text("a.bin", "application/octet-stream", b"raw") == "raw"


def test_slugify():
    assert slugify("Hello World") == "hello-world"
    assert slugify("技术部") == "技术部"  # 中文保留
    assert slugify("  A / B  ") == "a-b"
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/ingest/parser.py`**

```python
import re


def parse_to_text(filename: str, content_type: str, data: bytes) -> str:
    """文件字节 → 纯文本。MD/TXT 直接解码；PDF 用 pypdf 提取文本层。"""
    lower = filename.lower()
    if lower.endswith(".pdf") or content_type == "application/pdf":
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def slugify(text: str) -> str:
    """生成 slug：去首尾空白，非字母数字（保留中日韩等非 ASCII）转连字符，ASCII 转小写。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w一-鿿]+", "-", text, flags=re.UNICODE)
    return text.strip("-")
```

- [ ] **Step 4：写失败测试 `tests/test_pipeline.py`**

```python
import json

from app.ingest.pipeline import PageDraft, analyze, extract_wikilinks, generate_pages
from tests.fakes import FakeLLM


async def test_analyze_parses_json_with_fences():
    analysis = {"entities": ["A"], "concepts": ["B"], "key_claims": [],
                "links_to_existing": [], "contradictions": []}
    llm = FakeLLM(["```json\n" + json.dumps(analysis) + "\n```"])
    out = await analyze(llm, "some text")
    assert out["entities"] == ["A"] and out["concepts"] == ["B"]


async def test_analyze_falls_back_on_bad_json():
    llm = FakeLLM(["not json at all"])
    out = await analyze(llm, "text")
    assert out == {"entities": [], "concepts": [], "key_claims": [],
                   "links_to_existing": [], "contradictions": []}


async def test_generate_pages_parses_and_constrains_page_type():
    pages = [
        {"title": "实体A", "slug": "实体A", "page_type": "entity", "content_md": "见 [[概念B]]"},
        {"title": "怪类型", "slug": "x", "page_type": "bogus", "content_md": "y"},
    ]
    llm = FakeLLM(["```json\n" + json.dumps(pages) + "\n```"])
    drafts = await generate_pages(llm, {"entities": ["A"]}, index_md="")
    assert all(isinstance(d, PageDraft) for d in drafts)
    types = {d.page_type for d in drafts}
    assert "entity" in types
    assert "bogus" not in types and "concept" in types  # 非法类型降级为 concept


def test_extract_wikilinks():
    assert extract_wikilinks("见 [[概念B]] 与 [[实体A]]，再引 [[概念B]]") == ["概念B", "实体A"]
```

- [ ] **Step 5：运行测试，确认失败**。

- [ ] **Step 6：实现 `app/ingest/pipeline.py`**

```python
import json
import re
from dataclasses import dataclass, field

from app.ingest.parser import slugify
from app.models.wiki_page import PAGE_TYPES

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_ANALYZE_KEYS = ("entities", "concepts", "key_claims", "links_to_existing", "contradictions")

ANALYZE_SYSTEM = (
    "你是知识抽取器。阅读文本，输出 JSON，键为 "
    "entities/concepts/key_claims/links_to_existing/contradictions，值均为字符串数组。只输出 JSON。"
)
GENERATE_SYSTEM = (
    "你是 wiki 编辑。依据分析结果与现有目录，产出 wiki 页 JSON 数组；"
    "每项含 title/slug/page_type/content_md，page_type ∈ "
    "[source_summary,entity,concept,overview]，正文用 [[wikilink]] 交叉引用。只输出 JSON 数组。"
)


@dataclass
class PageDraft:
    title: str
    slug: str
    page_type: str
    content_md: str
    frontmatter: dict = field(default_factory=dict)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


async def analyze(llm, text: str) -> dict:
    raw = await llm.complete(ANALYZE_SYSTEM, text)
    try:
        data = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {k: (data.get(k) if isinstance(data.get(k), list) else []) for k in _ANALYZE_KEYS}


async def generate_pages(llm, analysis: dict, index_md: str) -> list[PageDraft]:
    user = f"分析结果:\n{json.dumps(analysis, ensure_ascii=False)}\n\n现有目录:\n{index_md}"
    raw = await llm.complete(GENERATE_SYSTEM, user)
    try:
        items = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        items = []
    if not isinstance(items, list):
        items = []
    drafts: list[PageDraft] = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        ptype = it.get("page_type")
        if ptype not in PAGE_TYPES or ptype == "index":
            ptype = "concept"  # 非法或保留类型降级
        title = str(it["title"])
        drafts.append(
            PageDraft(
                title=title,
                slug=slugify(str(it.get("slug") or title)),
                page_type=ptype,
                content_md=str(it.get("content_md", "")),
            )
        )
    return drafts


def extract_wikilinks(content_md: str) -> list[str]:
    """提取 [[目标]] 的 slug 列表（去重保序）。"""
    slugs = [slugify(m.group(1)) for m in _WIKILINK.finditer(content_md)]
    return list(dict.fromkeys(slugs))
```

- [ ] **Step 7：运行测试，确认通过**；**Step 8：提交**

```bash
git add api/app/ingest/ api/tests/test_parser.py api/tests/test_pipeline.py
git commit -m "feat(ingest): parser（MD/TXT/PDF→文本、slugify）+ 两步 pipeline（analyze/generate/wikilink）"
```

---

### Task 7：摄入编排 ingest_service（crown jewel）

**Files:**
- Create: `api/app/services/ingest_service.py`
- Test: `api/tests/test_ingest_service.py`

- [ ] **Step 1：写失败测试 `tests/test_ingest_service.py`（核心不变量）**

```python
import json

import pytest_asyncio

from app.models import KnowledgeBase, User
from app.repositories import kb_repo, source_repo, wiki_repo
from app.services import ingest_service
from tests.fakes import FakeLLM, FakeStorage


def _llm(analysis: dict, pages: list[dict]) -> FakeLLM:
    return FakeLLM([json.dumps(analysis), json.dumps(pages)])


@pytest_asyncio.fixture
async def kb_and_source(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add_all([kb, u])
    await session.flush()
    storage = FakeStorage()
    storage.put("k1", "技术部负责后端。".encode(), "text/markdown")
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k1",
    )
    await session.flush()
    return kb, src, storage


async def test_pages_have_sources_and_links(session, kb_and_source):
    kb, src, storage = kb_and_source
    llm = _llm(
        {"entities": ["技术部"], "concepts": ["后端"]},
        [
            {"title": "技术部", "slug": "技术部", "page_type": "entity",
             "content_md": "技术部，见 [[后端]]"},
            {"title": "后端", "slug": "后端", "page_type": "concept", "content_md": "后端开发"},
            {"title": "源摘要", "slug": "源摘要", "page_type": "source_summary", "content_md": "摘要"},
        ],
    )
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()

    pages = {p.slug: p for p in await wiki_repo.list_by_kb(session, kb.id)}
    assert "技术部" in pages and "后端" in pages
    # 每个内容页都带本 source 的溯源
    assert str(src.id) in pages["技术部"].source_ids
    # wikilink 已写入并回填
    links = await wiki_repo.links_from(session, pages["技术部"].id)
    assert any(l.to_slug == "后端" and l.to_page_id == pages["后端"].id for l in links)
    # index 目录页自动生成
    assert "index" in {p.page_type for p in pages.values()}
    # 状态完成
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.status == "done"


async def test_fallback_summary_when_llm_omits(session, kb_and_source):
    kb, src, storage = kb_and_source
    # LLM 只产出 entity，没有 source_summary
    llm = _llm(
        {"entities": ["X"]},
        [{"title": "X", "slug": "x", "page_type": "entity", "content_md": "x"}],
    )
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()
    pages = await wiki_repo.list_by_kb(session, kb.id)
    assert any(p.page_type == "source_summary" for p in pages)  # 兜底补齐


async def test_idempotent_rerun(session, kb_and_source):
    kb, src, storage = kb_and_source
    pages_json = [{"title": "X", "slug": "x", "page_type": "entity", "content_md": "x"}]
    await ingest_service.ingest_source(
        session, src.id, llm=_llm({"entities": ["X"]}, pages_json), storage=storage
    )
    await session.flush()
    n1 = len(await wiki_repo.list_by_kb(session, kb.id))
    await ingest_service.ingest_source(
        session, src.id, llm=_llm({"entities": ["X"]}, pages_json), storage=storage
    )
    await session.flush()
    n2 = len(await wiki_repo.list_by_kb(session, kb.id))
    assert n1 == n2  # 重跑不产生重复页


async def test_failure_sets_status_failed(session, kb_and_source):
    kb, src, storage = kb_and_source

    class BoomLLM:
        async def complete(self, system, user):
            raise RuntimeError("llm down")

    await ingest_service.ingest_source(session, src.id, llm=BoomLLM(), storage=storage)
    await session.flush()
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.status == "failed" and "llm down" in (refreshed.error or "")
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/services/ingest_service.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest import parser, pipeline
from app.integrations.storage import StorageBackend
from app.repositories import source_repo, wiki_repo


def _index_markdown(pages) -> str:
    """按 page_type 分组列出非 index 页，生成目录 markdown。"""
    groups: dict[str, list] = {}
    for p in pages:
        if p.page_type == "index":
            continue
        groups.setdefault(p.page_type, []).append(p)
    lines = ["# 目录（index）", ""]
    for ptype in ("overview", "entity", "concept", "source_summary"):
        items = groups.get(ptype)
        if not items:
            continue
        lines.append(f"## {ptype}")
        for p in sorted(items, key=lambda x: x.title):
            lines.append(f"- [[{p.slug}]] {p.title}")
        lines.append("")
    return "\n".join(lines)


async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    *,
    llm,
    storage: StorageBackend,
) -> None:
    """确定性两步摄入：解析→分析→生成→落页→链接图→重建 index。失败置 failed。"""
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        return
    try:
        await source_repo.set_status(session, source_id, "processing")

        data = storage.get(src.storage_key)
        text = parser.parse_to_text(src.filename, src.content_type, data)

        analysis = await pipeline.analyze(llm, text)

        index_page = await wiki_repo.get_by_slug(session, src.kb_id, "index")
        index_md = index_page.content_md if index_page else ""
        drafts = await pipeline.generate_pages(llm, analysis, index_md)

        # 护栏：必含至少 1 个 source_summary，漏了用模板兜底
        if not any(d.page_type == "source_summary" for d in drafts):
            drafts.append(
                pipeline.PageDraft(
                    title=f"源摘要：{src.filename}",
                    slug=parser.slugify(f"summary-{src.id}"),
                    page_type="source_summary",
                    content_md=f"# {src.filename} 摘要\n\n（自动兜底）实体：{analysis.get('entities')}",
                )
            )

        sid = str(src.id)
        for d in drafts:
            existing = await wiki_repo.get_by_slug(session, src.kb_id, d.slug)
            merged_sources = list(dict.fromkeys((existing.source_ids if existing else []) + [sid]))
            page = await wiki_repo.upsert(
                session,
                kb_id=src.kb_id,
                slug=d.slug,
                title=d.title,
                page_type=d.page_type,
                content_md=d.content_md,
                frontmatter={**d.frontmatter, "type": d.page_type, "sources": merged_sources},
                source_ids=merged_sources,
            )
            await session.flush()
            await wiki_repo.replace_links(
                session, from_page_id=page.id, to_slugs=pipeline.extract_wikilinks(d.content_md)
            )

        await session.flush()
        # 重建 index 目录页
        pages = await wiki_repo.list_by_kb(session, src.kb_id)
        await wiki_repo.upsert(
            session,
            kb_id=src.kb_id,
            slug="index",
            title="目录",
            page_type="index",
            content_md=_index_markdown(pages),
            frontmatter={"type": "index"},
            source_ids=[],
        )
        await session.flush()
        # 回填 wikilink 目标
        await wiki_repo.backfill_link_targets(session, kb_id=src.kb_id)

        await source_repo.set_status(session, source_id, "done")
    except Exception as exc:  # noqa: BLE001 — 摄入失败要落库可观测
        await source_repo.set_status(session, source_id, "failed", error=str(exc))
```

- [ ] **Step 4：运行测试，确认通过**（**本计划最关键门槛**）；**Step 5：提交**

```bash
git add api/app/services/ingest_service.py api/tests/test_ingest_service.py
git commit -m "feat(ingest): ingest_service 两步摄入编排（溯源/兜底/幂等/链接图/index 重建）"
```

---

### Task 8：worker 队列与任务（queue + tasks + 注册）

**Files:**
- Create: `api/app/worker/queue.py`、`api/app/worker/tasks.py`
- Modify: `api/app/worker/settings.py`
- Test: `api/tests/test_worker_wiring.py`

> arq 真实入队是集成关注点；本任务单测只验证装配：`WorkerSettings.functions` 含 `ingest_source`、`tasks.ingest_source` 可导入。

- [ ] **Step 1：写失败测试 `tests/test_worker_wiring.py`**

```python
from app.worker import tasks
from app.worker.settings import WorkerSettings


def test_ingest_task_registered():
    assert tasks.ingest_source in WorkerSettings.functions
    assert callable(tasks.ingest_source)
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/worker/queue.py`**（arq 连接 + 入队封装）

```python
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_ingest(source_id: str) -> str:
    """入队 ingest_source，返回 arq job_id。"""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        job = await pool.enqueue_job("ingest_source", source_id)
        return job.job_id
    finally:
        await pool.close()
```

- [ ] **Step 4：实现 `app/worker/tasks.py`**（薄：装配真实依赖，调 service）

```python
import uuid

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.llm import LLMClient
from app.integrations.storage import MinioStorage
from app.services import ingest_service


async def ingest_source(ctx: dict, source_id: str) -> None:
    llm = LLMClient(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
    )
    storage = MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_sources,
        secure=settings.minio_secure,
    )
    async with SessionLocal() as session:
        await ingest_service.ingest_source(
            session, uuid.UUID(source_id), llm=llm, storage=storage
        )
        await session.commit()
```

- [ ] **Step 5：改 `app/worker/settings.py` 注册任务**

```python
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import ingest_source


class WorkerSettings:
    functions = [ingest_source]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = settings.arq_max_tries
    job_timeout = settings.arq_job_timeout
```

- [ ] **Step 6：运行测试，确认通过**；**Step 7：提交**

```bash
git add api/app/worker/queue.py api/app/worker/tasks.py api/app/worker/settings.py api/tests/test_worker_wiring.py
git commit -m "feat(worker): arq enqueue 封装 + ingest_source 任务 + 注册到 WorkerSettings"
```

---

### Task 9：上传控制器 sources + 路由 + API 测试

**Files:**
- Create: `api/app/schemas/source.py`、`api/app/controllers/sources.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_api_sources.py`

- [ ] **Step 1：实现 `app/schemas/source.py`**

```python
import uuid

from pydantic import BaseModel


class SourceOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    filename: str
    content_type: str
    status: str
    error: str | None = None
    job_id: str | None = None

    model_config = {"from_attributes": True}


class SourceCreatedOut(BaseModel):
    source_id: uuid.UUID
    status: str
```

- [ ] **Step 2：写失败测试 `tests/test_api_sources.py`**

> 用依赖覆盖把 `StorageBackend` 和"入队"换成测试替身，避免连真 MinIO/Redis；断言鉴权 + 落库 + 返回。

```python
import uuid

from app.core.deps import get_current_user
from app.controllers import sources as sources_ctrl
from app.main import app
from app.repositories import kb_repo, source_repo
from app.services import org_service
from tests.fakes import FakeStorage


async def _setup_user_kb(session, role="admin"):
    user = await org_service.create_user(
        session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role
    )
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    return user, kb


async def test_upload_creates_pending_source(session, client):
    user, kb = await _setup_user_kb(session)
    await session.commit()

    fake_storage = FakeStorage()
    enqueued: list[str] = []

    app.dependency_overrides[sources_ctrl.get_storage] = lambda: fake_storage
    app.dependency_overrides[get_current_user] = lambda: user

    async def _fake_enqueue(source_id: str) -> str:
        enqueued.append(source_id)
        return "job-xyz"

    sources_ctrl.enqueue_ingest = _fake_enqueue  # monkeypatch 入队
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        sid = body["source_id"]
        assert enqueued == [sid]
        # 落库且 job_id 回写
        refreshed = await source_repo.get_by_id(session, uuid.UUID(sid))
        assert refreshed.status == "pending" and refreshed.job_id == "job-xyz"
        assert fake_storage.objects  # 文件已存储
    finally:
        app.dependency_overrides.pop(sources_ctrl.get_storage, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_upload_forbidden_without_write(session, client):
    # 普通 user 对 company KB 无写权限
    user, kb = await _setup_user_kb(session, role="user")
    await session.commit()
    app.dependency_overrides[sources_ctrl.get_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(sources_ctrl.get_storage, None)
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 3：运行测试，确认失败**。

- [ ] **Step 4：实现 `app/controllers/sources.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations.storage import MinioStorage, StorageBackend
from app.models import User
from app.repositories import kb_repo, source_repo
from app.schemas.source import SourceCreatedOut, SourceOut
from app.services import permission_service
from app.worker.queue import enqueue_ingest

router = APIRouter(tags=["sources"])


def get_storage() -> StorageBackend:
    return MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_sources,
        secure=settings.minio_secure,
    )


@router.post("/kbs/{kb_id}/sources", response_model=SourceCreatedOut)
async def upload_source(
    kb_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    kb = await kb_repo.get_by_id(session, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kb not found")
    if not await permission_service.can_write(session, user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no write permission")

    data = await file.read()
    src = await source_repo.create(
        session,
        kb_id=kb_id,
        uploader_id=user.id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        storage_key="",  # 落库拿到 id 后再定 key
    )
    await session.flush()
    storage_key = f"{kb_id}/{src.id}/{src.filename}"
    storage.put(storage_key, data, src.content_type)
    src.storage_key = storage_key

    job_id = await enqueue_ingest(str(src.id))
    await source_repo.set_job_id(session, src.id, job_id)
    await session.commit()
    return SourceCreatedOut(source_id=src.id, status=src.status)


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if src.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return src
```

> 依赖说明：`kb_repo.get_by_id` 在子计划 2 未实现则需补一个最小 `get_by_id`（见 Step 5）。

- [ ] **Step 5：确保 `app/repositories/kb_repo.py` 有 `get_by_id`**（无则新增）

```python
async def get_by_id(session: AsyncSession, kb_id: uuid.UUID) -> KnowledgeBase | None:
    res = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    return res.scalar_one_or_none()
```

- [ ] **Step 6：改 `app/main.py` 注册路由**

```python
from fastapi import FastAPI

from app.controllers import auth, health, kb, org, sources


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Wiki API")
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(org.router, prefix="/api")
    app.include_router(kb.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 7：运行全量测试** `cd api && .venv/Scripts/python.exe -m pytest -q` → 全绿（子计划 1+2 的 18 个 + 本计划新增）。

- [ ] **Step 8：提交**

```bash
git add api/app/schemas/source.py api/app/controllers/sources.py api/app/repositories/kb_repo.py api/app/main.py api/tests/test_api_sources.py
git commit -m "feat(api): sources 上传/查询控制器（can_write 鉴权 + 存储 + 入队 + job_id 回写）"
```

---

## Self-Review（计划自检）

- **Spec 覆盖**：覆盖 spec 第 4（源上传/解析，MD/TXT/PDF）、第 5（sources/wiki_pages/page_links 模型）、第 7（MinIO 布局 + StorageBackend 抽象）、第 8（确定性两步摄入：解析→分析→生成→落页带 source_ids→链接图→重建 index→状态流转/失败落库；护栏：page_type 枚举、强制 sources[]、漏 summary 兜底、幂等 upsert）、第 10（`POST /kbs/{id}/sources`、`GET /sources/{id}`）、第 12（integrations/ingest/worker 分层）。✓
  - **明确不在本计划**：tsvector/trgm 全文检索列与 `search_tsv` 刷新（spec 第 8 步 8、第 9 节）→ 子计划 4（检索问答）；wiki 浏览端点 `GET /kbs/{id}/pages`、`GET /pages/{id}`（spec 第 6 功能、第 10）→ 子计划 4/5。
- **占位符扫描**：无 TODO/TBD；每个代码步骤含完整代码。✓
- **类型/命名一致**：`source_repo.{create,get_by_id,set_status,set_job_id,list_by_kb}`、`wiki_repo.{get_by_slug,get_by_id,list_by_kb,upsert,replace_links,links_from,backfill_link_targets}`、`pipeline.{analyze,generate_pages,extract_wikilinks,PageDraft}`、`parser.{parse_to_text,slugify}`、`ingest_service.ingest_source(session, source_id, *, llm, storage)`、`LLMClient.complete(system,user)`、`StorageBackend.{put,get,presigned_url}`、`enqueue_ingest(source_id)->job_id` 在各 Task 引用一致。✓
- **依赖顺序**：models→migration→repos(source/wiki)→integrations→parser/pipeline→ingest_service→worker→controller 单向无环。✓
- **CLAUDE.md 合规**：迁移 0003 用 `alembic revision` 生成骨架再填正文（Task 2），不手写整文件。✓
- **可测性**：`ingest_service` 用 DI 注入 `llm`/`storage`，测试以 `FakeLLM`/`FakeStorage` 绕过 arq 直接 await；上传端点用 `app.dependency_overrides` 覆盖 `get_storage`/`get_current_user` 并 monkeypatch `enqueue_ingest`，不连真 MinIO/Redis。✓

## 执行交接

计划已存 `docs/superpowers/plans/2026-06-13-mvp-plan-03-sources-ingest.md`。老板已指示"接着做、每步自动提交"，故按 **executing-plans（本会话逐任务 + 检查点）** 推进：Task1→9 顺序实现，每个 Task 跑测试全绿后立即提交。

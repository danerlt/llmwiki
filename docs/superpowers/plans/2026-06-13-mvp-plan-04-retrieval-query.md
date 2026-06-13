# 子计划 4：检索与问答（关键词 + 图导航 + 目录，无向量）— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 executing-plans 逐任务实现。步骤用 `- [ ]` 勾选跟踪。每个代码步骤先写失败测试、看它失败、再写最小实现、看它通过、提交（TDD）。

**Goal:** 实现权限感知的检索问答闭环：关键词召回（可移植子串匹配 + Postgres trgm 索引）→ 沿 `page_links` 与共享 `source_ids` 的图扩展 → 附上各 KB 的 index 目录 → **严格按 `accessible_kb_ids(user)` 过滤** → 组装编号上下文交 LLM 生成带引用的回答。落地 `/search`、`/query` 与 wiki 浏览端点 `/kbs/{id}/pages`、`/pages/{id}`。

**Architecture:** Controller–Service–Repository 分层。检索逻辑集中在 `services/retrieval_service.py`（召回+图扩展+目录+权限过滤），问答在 `services/query_service.py`（组装上下文+调 LLM+引用），LLM 用依赖注入便于 mock。关键词查询用**可移植 `lower(col) LIKE '%q%'`**（SQLite/Postgres 通用），Postgres 侧用 `gin_trgm_ops` 索引加速（迁移 0004）。

**Tech Stack:** FastAPI、SQLAlchemy 2.0(async)、Postgres pg_trgm（仅索引层）、httpx(LLM)、pytest+aiosqlite。

**Definition of Done:**
- ①`pytest` 全绿，含**权限不变量用例**：检索/搜索结果永不含调用者不可见 KB 的页（即使关键词命中）；
- ②`GET /api/search?q=&kb=` 返回按权限过滤的页列表（不调生成 LLM）；
- ③`POST /api/query` 返回 `{answer, citations:[{page_id,title,kb_id}]}`，引用只来自可见 KB；
- ④`GET /api/kbs/{id}/pages`、`GET /api/pages/{id}` 经权限校验；
- ⑤`alembic` 链延伸到 0004（trgm 索引，用 `alembic revision` 生成骨架后填正文）。

**测试基础设施决策:** 沿用 `sqlite+aiosqlite:///:memory:`。关键词查询用可移植 `func.lower(col).like(pattern)`，SQLite/Postgres 行为一致；trgm GIN 索引是 Postgres 专属**性能**优化（只在迁移里，不影响查询语义、不被 SQLite 测试触及）。共享源(`source_ids` JSON 数组)的重叠判定在 Python 层做（JSON 数组交集不易跨库 SQL 化），MVP 规模可接受。

---

## 文件结构（本计划产出/修改）

```
api/
  app/
    repositories/wiki_repo.py          # 修改：search_pages / linked_pages / list_by_kbs
    services/
      retrieval_service.py             # 新增：召回+图扩展+目录+权限过滤（crown jewel）
      query_service.py                 # 新增：组装上下文+LLM 生成+引用
    schemas/
      wiki.py query.py                 # 新增：PageOut/PageDetailOut、QueryRequest/AnswerOut/Citation
    controllers/
      search.py query.py wiki.py       # 新增：/search、/query、/kbs/{id}/pages、/pages/{id}
    main.py                            # 修改：注册新路由
  migrations/versions/<rev>_trgm_indexes.py   # 新增（alembic revision 生成）
  tests/
    test_retrieval_service.py test_query_service.py
    test_api_search_query.py test_api_wiki.py
```

> 测试统一命令：`cd api && .venv/Scripts/python.exe -m pytest <路径> -q`

---

### Task 1：wiki_repo 检索方法（关键词 / 链接 / 批量）

**Files:**
- Modify: `api/app/repositories/wiki_repo.py`
- Test: `api/tests/test_retrieval_repo.py`

- [ ] **Step 1：写失败测试 `tests/test_retrieval_repo.py`**

```python
from app.models import KnowledgeBase
from app.repositories import wiki_repo


async def _kb(session, name="公司"):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name=name)
    session.add(kb)
    await session.flush()
    return kb


async def test_search_pages_matches_title_and_body_and_skips_index(session):
    kb = await _kb(session)
    await wiki_repo.upsert(session, kb_id=kb.id, slug="后端", title="后端",
                           page_type="entity", content_md="负责服务端", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="前端", title="前端",
                           page_type="entity", content_md="提到后端协作", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="index", title="目录",
                           page_type="index", content_md="后端 前端", frontmatter={}, source_ids=[])
    await session.flush()
    hits = await wiki_repo.search_pages(session, [kb.id], "后端", limit=10)
    slugs = [p.slug for p in hits]
    assert "后端" in slugs and "前端" in slugs   # 标题命中 + 正文命中
    assert "index" not in slugs                  # index 不作为种子
    assert hits[0].slug == "后端"                # 标题命中排前


async def test_linked_pages_returns_resolved_targets(session):
    kb = await _kb(session)
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="a", title="A",
                               page_type="entity", content_md="见 [[b]]", frontmatter={}, source_ids=[])
    b = await wiki_repo.upsert(session, kb_id=kb.id, slug="b", title="B",
                               page_type="concept", content_md="x", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["b"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    linked = await wiki_repo.linked_pages(session, [a.id])
    assert [p.id for p in linked] == [b.id]


async def test_list_by_kbs(session):
    kb1 = await _kb(session, "kb1")
    kb2 = await _kb(session, "kb2")
    await wiki_repo.upsert(session, kb_id=kb1.id, slug="p1", title="P1",
                           page_type="entity", content_md="", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb2.id, slug="p2", title="P2",
                           page_type="entity", content_md="", frontmatter={}, source_ids=[])
    await session.flush()
    pages = await wiki_repo.list_by_kbs(session, [kb1.id, kb2.id])
    assert {p.slug for p in pages} == {"p1", "p2"}
```

- [ ] **Step 2：运行测试，确认失败** —— `AttributeError: module 'app.repositories.wiki_repo' has no attribute 'search_pages'`。

- [ ] **Step 3：在 `app/repositories/wiki_repo.py` 顶部补 import 并追加方法**

把首行 import 改为（追加 `func`、`or_`）：
```python
from sqlalchemy import delete, func, or_, select
```

在文件末尾追加：
```python
async def search_pages(
    session: AsyncSession, kb_ids: list[uuid.UUID], q: str, limit: int = 20
) -> list[WikiPage]:
    """可移植关键词召回：标题/正文子串匹配（lower+LIKE），排除 index，标题命中排前。"""
    if not kb_ids or not q:
        return []
    pattern = f"%{q.lower()}%"
    title_match = func.lower(WikiPage.title).like(pattern)
    body_match = func.lower(WikiPage.content_md).like(pattern)
    stmt = (
        select(WikiPage)
        .where(
            WikiPage.kb_id.in_(kb_ids),
            WikiPage.page_type != "index",
            or_(title_match, body_match),
        )
        .order_by(title_match.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def linked_pages(
    session: AsyncSession, from_page_ids: list[uuid.UUID]
) -> list[WikiPage]:
    """种子页经 page_links 直接链接、且已回填 to_page_id 的目标页。"""
    if not from_page_ids:
        return []
    stmt = (
        select(WikiPage)
        .join(PageLink, PageLink.to_page_id == WikiPage.id)
        .where(PageLink.from_page_id.in_(from_page_ids), PageLink.to_page_id.is_not(None))
    )
    res = await session.execute(stmt)
    return list(res.scalars().unique().all())


async def list_by_kbs(session: AsyncSession, kb_ids: list[uuid.UUID]) -> list[WikiPage]:
    if not kb_ids:
        return []
    res = await session.execute(select(WikiPage).where(WikiPage.kb_id.in_(kb_ids)))
    return list(res.scalars().all())
```

- [ ] **Step 4：运行测试，确认通过**；**Step 5：提交**

```bash
git add api/app/repositories/wiki_repo.py api/tests/test_retrieval_repo.py
git commit -m "feat(repo): wiki_repo 检索方法（关键词子串召回/链接目标/批量列举）"
```

---

### Task 2：迁移 0004（Postgres trgm GIN 索引）

> CLAUDE.md：用 `alembic revision` 生成骨架，再填正文。索引为 Postgres 专属性能优化，SQLite 测试不触及。

**Files:**
- Create（由命令生成）: `api/migrations/versions/<rev>_trgm_indexes.py`

- [ ] **Step 1：生成骨架** —— `cd api && .venv/Scripts/python.exe -m alembic revision -m "trgm indexes"`，确认 `down_revision = "56b57887b971"`（上一 head）。

- [ ] **Step 2：填 `upgrade()` / `downgrade()`**

```python
def upgrade() -> None:
    # pg_trgm 扩展已在 0001 基线启用；此处为标题/正文建 GIN trgm 索引加速 LIKE 子串检索
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wiki_title_trgm "
        "ON wiki_pages USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wiki_content_trgm "
        "ON wiki_pages USING gin (content_md gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_wiki_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_wiki_title_trgm")
```

- [ ] **Step 3：验证链** —— `cd api && .venv/Scripts/python.exe -m alembic history` 列出 `... -> <rev> (head)`。

- [ ] **Step 4：提交**

```bash
git add api/migrations/versions/
git commit -m "feat(db): 迁移 0004 为 wiki_pages 标题/正文建 trgm GIN 索引"
```

---

### Task 3：retrieval_service（召回+图扩展+目录+权限过滤，crown jewel）

**Files:**
- Create: `api/app/services/retrieval_service.py`
- Test: `api/tests/test_retrieval_service.py`

- [ ] **Step 1：写失败测试 `tests/test_retrieval_service.py`（权限不变量为核心）**

```python
import pytest_asyncio

from app.repositories import kb_repo, org_repo, wiki_repo
from app.services import retrieval_service
from app.services import org_service


@pytest_asyncio.fixture
async def org(session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    company_kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    tech_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=tech.id, name="技术部")
    backend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=backend.id, name="后端组")
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice",
        department_id=backend.id,
    )
    await session.flush()
    # 每个 KB 都放一个含关键词“后端”的页
    for kb in (company_kb, tech_kb, backend_kb, frontend_kb):
        await wiki_repo.upsert(session, kb_id=kb.id, slug=f"p-{kb.id}", title="后端话题",
                               page_type="entity", content_md="讲后端", frontmatter={}, source_ids=[])
    await session.flush()
    return {"alice": alice, "frontend_kb": frontend_kb, "backend_kb": backend_kb}


async def test_retrieve_never_returns_inaccessible_kb(session, org):
    pages = await retrieval_service.retrieve(session, org["alice"], "后端")
    kb_ids = {p.kb_id for p in pages}
    assert org["frontend_kb"].id not in kb_ids   # 平级前端组不可见——铁律
    assert org["backend_kb"].id in kb_ids         # 本部门可见
    assert pages, "应召回到可见 KB 的页"


async def test_graph_expansion_pulls_linked_pages(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    # admin 可见 company
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.flush()
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="种子", title="种子页",
                               page_type="entity", content_md="关键词X，见 [[相关]]",
                               frontmatter={}, source_ids=[])
    rel = await wiki_repo.upsert(session, kb_id=kb.id, slug="相关", title="相关页",
                                 page_type="concept", content_md="无关键词", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["相关"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    pages = await retrieval_service.retrieve(session, admin, "关键词X")
    slugs = {p.slug for p in pages}
    assert "种子" in slugs and "相关" in slugs   # 图扩展拉入直接链接页（虽不含关键词）
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/services/retrieval_service.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WikiPage
from app.repositories import wiki_repo
from app.services import permission_service


async def retrieve(
    session: AsyncSession,
    user: User,
    q: str,
    kb_scope: list[uuid.UUID] | None = None,
    limit: int = 10,
) -> list[WikiPage]:
    """权限感知检索：关键词召回 → page_links/共享源图扩展 → 附 index 目录。
    铁律：返回集合中每页 kb_id 必属 accessible_kb_ids(user)。"""
    kb_ids = await permission_service.accessible_kb_ids(session, user)
    if kb_scope is not None:
        kb_ids = kb_ids & set(kb_scope)
    if not kb_ids:
        return []
    kb_id_list = list(kb_ids)

    seeds = await wiki_repo.search_pages(session, kb_id_list, q, limit=limit)
    result: dict[uuid.UUID, WikiPage] = {p.id: p for p in seeds}

    # 图扩展 1：page_links 直接链接（已回填 to_page_id）
    linked = await wiki_repo.linked_pages(session, list(result.keys()))
    for p in linked:
        if p.kb_id in kb_ids:  # 权限再过滤
            result.setdefault(p.id, p)

    # 图扩展 2：共享 source_ids（Python 交集）
    seed_sources = {sid for p in seeds for sid in (p.source_ids or [])}
    if seed_sources:
        for p in await wiki_repo.list_by_kbs(session, kb_id_list):
            if seed_sources & set(p.source_ids or []):
                result.setdefault(p.id, p)

    # 附上涉及 KB 的 index 目录页
    for kb_id in {p.kb_id for p in result.values()}:
        idx = await wiki_repo.get_by_slug(session, kb_id, "index")
        if idx is not None and idx.kb_id in kb_ids:
            result.setdefault(idx.id, idx)

    return list(result.values())
```

- [ ] **Step 4：运行测试，确认通过（权限不变量是本计划最关键门槛）**；**Step 5：提交**

```bash
git add api/app/services/retrieval_service.py api/tests/test_retrieval_service.py
git commit -m "feat(retrieval): retrieval_service（关键词召回+图扩展+目录，严格可见 KB 过滤）"
```

---

### Task 4：schemas（wiki + query）

**Files:**
- Create: `api/app/schemas/wiki.py`、`api/app/schemas/query.py`

- [ ] **Step 1：实现 `app/schemas/wiki.py`**

```python
import uuid

from pydantic import BaseModel


class PageOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    slug: str
    page_type: str

    model_config = {"from_attributes": True}


class PageDetailOut(PageOut):
    content_md: str
    frontmatter: dict
    source_ids: list[str]
```

- [ ] **Step 2：实现 `app/schemas/query.py`**

```python
import uuid

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    kb_scope: list[uuid.UUID] | None = None


class Citation(BaseModel):
    page_id: uuid.UUID
    title: str
    kb_id: uuid.UUID


class AnswerOut(BaseModel):
    answer: str
    citations: list[Citation]
```

- [ ] **Step 3：无独立单测（由 Task 5/6 覆盖）。提交**

```bash
git add api/app/schemas/wiki.py api/app/schemas/query.py
git commit -m "feat(schema): wiki PageOut/PageDetailOut、query QueryRequest/AnswerOut/Citation"
```

---

### Task 5：query_service（组装上下文 + LLM 生成 + 引用）

**Files:**
- Create: `api/app/services/query_service.py`
- Test: `api/tests/test_query_service.py`

- [ ] **Step 1：写失败测试 `tests/test_query_service.py`**

```python
from app.repositories import kb_repo, wiki_repo
from app.services import org_service, query_service
from tests.fakes import FakeLLM


async def test_answer_assembles_context_and_returns_citations(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.flush()
    await wiki_repo.upsert(session, kb_id=kb.id, slug="后端", title="后端",
                           page_type="entity", content_md="服务端开发", frontmatter={}, source_ids=[])
    await session.flush()

    llm = FakeLLM(["后端指服务端开发[1]。"])
    out = await query_service.answer(session, admin, "什么是后端", llm=llm)
    assert out["answer"] == "后端指服务端开发[1]。"
    assert any(c["title"] == "后端" for c in out["citations"])
    # LLM 收到的 user prompt 含编号资料
    assert "[1]" in llm.calls[0][1]


async def test_answer_empty_when_no_pages(session):
    admin = await org_service.create_user(
        session, email="a@x.com", password="pw123456", display_name="A", role="admin"
    )
    await session.flush()
    llm = FakeLLM(["不应被调用"])
    out = await query_service.answer(session, admin, "无关问题", llm=llm)
    assert out["citations"] == []
    assert llm.calls == []   # 无资料则不调用 LLM
```

- [ ] **Step 2：运行测试，确认失败**。

- [ ] **Step 3：实现 `app/services/query_service.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import retrieval_service

QUERY_SYSTEM = (
    "你是企业知识库问答助手。只依据给定编号资料回答，"
    "在句末用 [n] 标注引用；资料不足就说不知道。"
)
_PAGE_CHAR_BUDGET = 2000  # 每页正文截断上限


async def answer(
    session: AsyncSession, user: User, question: str,
    kb_scope=None, *, llm,
) -> dict:
    pages = await retrieval_service.retrieve(session, user, question, kb_scope)
    if not pages:
        return {"answer": "（无可用知识，无法回答）", "citations": []}

    parts: list[str] = []
    citations: list[dict] = []
    for i, p in enumerate(pages, 1):
        body = (p.content_md or "")[:_PAGE_CHAR_BUDGET]
        parts.append(f"[{i}] {p.title}\n{body}")
        citations.append({"page_id": p.id, "title": p.title, "kb_id": p.kb_id})

    user_prompt = f"问题：{question}\n\n资料：\n" + "\n\n".join(parts)
    answer_text = await llm.complete(QUERY_SYSTEM, user_prompt)
    return {"answer": answer_text, "citations": citations}
```

- [ ] **Step 4：运行测试，确认通过**；**Step 5：提交**

```bash
git add api/app/services/query_service.py api/tests/test_query_service.py
git commit -m "feat(query): query_service 组装编号上下文 + LLM 生成 + 引用（无资料不调 LLM）"
```

---

### Task 6：控制器 search / query / wiki + 路由 + API 测试

**Files:**
- Create: `api/app/controllers/search.py`、`api/app/controllers/query.py`、`api/app/controllers/wiki.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_api_search_query.py`、`api/tests/test_api_wiki.py`

- [ ] **Step 1：实现 `app/controllers/search.py`**

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import PageOut
from app.services import retrieval_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[PageOut])
async def search(
    q: str = Query(...),
    kb: list[uuid.UUID] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await retrieval_service.retrieve(session, user, q, kb_scope=kb)
```

- [ ] **Step 2：实现 `app/controllers/query.py`（LLMClient 用可覆盖依赖）**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations.llm import LLMClient
from app.models import User
from app.schemas.query import AnswerOut, QueryRequest
from app.services import query_service

router = APIRouter(tags=["query"])


def get_llm() -> LLMClient:
    return LLMClient(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
    )


@router.post("/query", response_model=AnswerOut)
async def query(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    return await query_service.answer(
        session, user, body.question, kb_scope=body.kb_scope, llm=llm
    )
```

- [ ] **Step 3：实现 `app/controllers/wiki.py`（浏览，权限校验）**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import wiki_repo
from app.schemas.wiki import PageDetailOut, PageOut
from app.services import permission_service

router = APIRouter(tags=["wiki"])


@router.get("/kbs/{kb_id}/pages", response_model=list[PageOut])
async def list_pages(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    accessible = await permission_service.accessible_kb_ids(session, user)
    if kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return await wiki_repo.list_by_kb(session, kb_id)


@router.get("/pages/{page_id}", response_model=PageDetailOut)
async def get_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return page
```

- [ ] **Step 4：改 `app/main.py` 注册路由**

```python
from app.controllers import auth, health, kb, org, query, search, sources, wiki
# create_app() 内追加：
    app.include_router(search.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(wiki.router, prefix="/api")
```

- [ ] **Step 5：写失败测试 `tests/test_api_search_query.py`（权限过滤 + 问答）**

```python
from app.controllers import query as query_ctrl
from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, org_repo, wiki_repo
from app.services import org_service
from tests.fakes import FakeLLM


async def _two_dept_kbs_with_pages(session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    backend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=backend.id, name="后端组")
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id
    )
    await session.flush()
    await wiki_repo.upsert(session, kb_id=backend_kb.id, slug="b", title="后端机密",
                           page_type="entity", content_md="后端内容", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=frontend_kb.id, slug="f", title="后端禁地",
                           page_type="entity", content_md="后端内容", frontmatter={}, source_ids=[])
    await session.flush()
    return alice, backend_kb, frontend_kb


async def test_search_filters_inaccessible(session, client):
    alice, backend_kb, frontend_kb = await _two_dept_kbs_with_pages(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.get("/api/search", params={"q": "后端"})
        assert r.status_code == 200
        kb_ids = {p["kb_id"] for p in r.json()}
        assert str(frontend_kb.id) not in kb_ids   # 平级前端组不可见——铁律
        assert str(backend_kb.id) in kb_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_query_returns_answer_and_citations(session, client):
    alice, backend_kb, frontend_kb = await _two_dept_kbs_with_pages(session)
    await session.commit()
    fake_llm = FakeLLM(["后端机密讲了后端内容[1]。"])
    app.dependency_overrides[get_current_user] = lambda: alice
    app.dependency_overrides[query_ctrl.get_llm] = lambda: fake_llm
    try:
        r = await client.post("/api/query", json={"question": "后端是什么"})
        assert r.status_code == 200
        body = r.json()
        assert "[1]" in body["answer"]
        cited_kbs = {c["kb_id"] for c in body["citations"]}
        assert str(frontend_kb.id) not in cited_kbs   # 引用只来自可见 KB
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(query_ctrl.get_llm, None)
```

- [ ] **Step 6：写失败测试 `tests/test_api_wiki.py`（浏览鉴权）**

```python
from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, org_repo, wiki_repo
from app.services import org_service


async def test_list_pages_forbidden_for_inaccessible_kb(session, client):
    frontend = await org_repo.create_department(session, name="前端组", parent_id=None)
    await session.flush()
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    backend = await org_repo.create_department(session, name="后端组", parent_id=None)
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.get(f"/api/kbs/{frontend_kb.id}/pages")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_get_page_detail_accessible(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    page = await wiki_repo.upsert(session, kb_id=kb.id, slug="p", title="P",
                                  page_type="entity", content_md="内容", frontmatter={}, source_ids=["s1"])
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get(f"/api/pages/{page.id}")
        assert r.status_code == 200
        assert r.json()["content_md"] == "内容"
        assert r.json()["source_ids"] == ["s1"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 7：运行全量测试** `cd api && .venv/Scripts/python.exe -m pytest -q` → 全绿。

- [ ] **Step 8：提交**

```bash
git add api/app/controllers/search.py api/app/controllers/query.py api/app/controllers/wiki.py api/app/main.py api/tests/test_api_search_query.py api/tests/test_api_wiki.py
git commit -m "feat(api): /search、/query、wiki 浏览端点（权限过滤 + 引用回答）"
```

---

## Self-Review（计划自检）

- **Spec 覆盖**：覆盖 spec 第 6（wiki 浏览）、第 8（关键词检索作用于 wiki_pages）、第 9（检索=全文/trgm 关键词 + page_links/共享源图扩展 + index 目录；`/search` 走召回不调生成 LLM；`/query` 组装编号上下文→LLM→带引用）、第 10（`/search`、`/query`、`/kbs/{id}/pages`、`/pages/{id}`）、第 6.3 铁律（结果严格按 `accessible_kb_ids` 过滤）。✓
  - **简化说明**：MVP 用可移植 `lower(col) LIKE` 子串召回（spec 允许"trgm 子串兜底"）+ Postgres trgm GIN 索引；tsvector 全文排序列作为 V2 增强，不进 ORM（保 SQLite 可测）。预算控制为每页正文 2000 字截断（spec 第 9 步 5 的精简版）。
- **占位符扫描**：无 TODO/TBD；每步完整代码。✓
- **类型/命名一致**：`wiki_repo.{search_pages,linked_pages,list_by_kbs,get_by_slug,get_by_id,list_by_kb}`、`retrieval_service.retrieve(session,user,q,kb_scope,limit)`、`query_service.answer(session,user,question,kb_scope,*,llm)->{answer,citations}`、`permission_service.accessible_kb_ids`、`query_ctrl.get_llm`、`PageOut/PageDetailOut/QueryRequest/AnswerOut/Citation` 一致。✓
- **依赖顺序**：wiki_repo→(migration)→retrieval_service→schemas→query_service→controllers 单向无环。✓
- **可测性**：检索/问答用 SQLite + 可移植查询；`/query` 的 LLM 经 `get_llm` 依赖覆盖为 `FakeLLM`，`get_current_user` 覆盖指定用户；权限不变量在 service 层与 API 层各测一遍。✓

## 执行交接

计划已存 `docs/superpowers/plans/2026-06-13-mvp-plan-04-retrieval-query.md`。按 executing-plans 本会话逐任务实现，每个 Task 跑测试全绿后立即提交。

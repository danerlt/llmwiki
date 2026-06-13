# 子计划 7：知识晋升 + Review 审核队列 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。后端 TDD，前端 build/test 通过即提交。迁移用 `alembic revision` 生成骨架。

**Goal（企业知识治理）:** 低作用域 KB（个人/团队）的 wiki 页可发起「晋升」到更高作用域 KB（部门/公司），经**有目标 KB 写权限的审核者**批准后复制过去并刷新目标 index。形成"提交→审核→晋升"的治理闭环。

**Architecture:** 新增 `promotion_requests` 表与 `PromotionRequest` 模型；`promotion_repo` 数据访问；`promotion_service` 编排 + 权限（申请须可读源页、审批须 `can_write(目标KB)`）；`kb_service.rebuild_index` 从 `ingest_service` 抽出复用（DRY）；`controllers/reviews.py` 暴露 promote / reviews / approve / reject；前端 `ReviewsPage` + 页详情"申请晋升"。

**Tech Stack:** 同前。权限复用 `permission_service.{accessible_kb_ids, can_write}`。

**Definition of Done:** ①后端 `pytest` 全绿，含权限不变量（非授权者不能审批/看不到队列、不能晋升不可读页）；②前端 build/test 绿；③docker 端到端：alice 把个人页申请晋升到公司 KB → admin 在审核页批准 → 该页出现在公司 KB。

---

### Task 1：模型 + 迁移 0005（promotion_requests）

**Files:** 新增 `api/app/models/promotion_request.py`；改 `api/app/models/__init__.py`；迁移（`alembic revision` 生成）；测试 `api/tests/test_promotion_model.py`

- [ ] **Step 1：写失败测试** `tests/test_promotion_model.py`

```python
from app.models import KnowledgeBase, PromotionRequest, User, WikiPage


async def test_promotion_request_persists(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="user")
    session.add_all([kb, u])
    await session.flush()
    page = WikiPage(kb_id=kb.id, title="P", slug="p", page_type="entity",
                    content_md="x", frontmatter={}, source_ids=[])
    session.add(page)
    await session.flush()
    pr = PromotionRequest(page_id=page.id, to_kb_id=kb.id, requested_by=u.id)
    session.add(pr)
    await session.flush()
    assert pr.status == "pending" and pr.reviewer_id is None
```

- [ ] **Step 2：模型** `app/models/promotion_request.py`

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PROMOTION_STATUSES = ("pending", "approved", "rejected")


class PromotionRequest(Base):
    __tablename__ = "promotion_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("wiki_pages.id"))
    to_kb_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("knowledge_bases.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3：`models/__init__.py` 注册** `PromotionRequest`（import + __all__）。

- [ ] **Step 4：跑测试 PASS。生成迁移** `cd api && .venv/Scripts/python.exe -m alembic revision -m "promotion requests"`，填 upgrade 建表（id/page_id→wiki_pages/to_kb_id→knowledge_bases/requested_by→users/status server_default pending/note/reviewer_id→users null/created_at/decided_at），downgrade drop_table；`alembic history` 确认链。**提交**。

```bash
git commit -m "feat(model): promotion_requests 模型 + 迁移 0005"
```

---

### Task 2：kb_service.rebuild_index 抽取 + promotion_repo + promotion_service（权限，crown jewel）

**Files:** 改 `api/app/services/kb_service.py`、`api/app/services/ingest_service.py`（复用 rebuild_index）；新增 `api/app/repositories/promotion_repo.py`、`api/app/services/promotion_service.py`；测试 `api/tests/test_promotion_service.py`

- [ ] **Step 1：`kb_service.py` 抽出 index 重建**（把 ingest_service 内 `_index_markdown` 逻辑移来）

```python
from app.repositories import kb_repo, wiki_repo  # 顶部已有 kb_repo? 按需补

def _index_markdown(pages) -> str:
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


async def rebuild_index(session, kb_id) -> None:
    pages = await wiki_repo.list_by_kb(session, kb_id)
    await wiki_repo.upsert(session, kb_id=kb_id, slug="index", title="目录",
                           page_type="index", content_md=_index_markdown(pages),
                           frontmatter={"type": "index"}, source_ids=[])
```

- [ ] **Step 2：`ingest_service.py` 改用 `kb_service.rebuild_index`**（删除内部 `_index_markdown` 与内联 index upsert，替换为 `await kb_service.rebuild_index(session, src.kb_id)`；其余 flush/backfill 不变）。跑 `tests/test_ingest_service.py` 确认无回归。

- [ ] **Step 3：写失败测试 `tests/test_promotion_service.py`（权限不变量）**

```python
import pytest_asyncio

from app.repositories import kb_repo, wiki_repo
from app.services import org_service, promotion_service


@pytest_asyncio.fixture
async def setup(session):
    company = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(session, email="admin@x.com", password="pw123456",
                                           display_name="Admin", role="admin")
    alice = await org_service.create_user(session, email="alice@x.com", password="pw123456",
                                          display_name="Alice", role="user")
    await session.flush()
    alice_kb = (await kb_repo.list_by_scope(session, "personal", alice.id))[0]
    page = await wiki_repo.upsert(session, kb_id=alice_kb.id, slug="想法", title="好想法",
                                  page_type="concept", content_md="内容", frontmatter={}, source_ids=["s1"])
    await session.flush()
    return {"company": company, "admin": admin, "alice": alice, "page": page}


async def test_alice_requests_admin_approves_promotes(session, setup):
    s = setup
    pr = await promotion_service.request_promotion(session, s["alice"], s["page"].id, s["company"].id, note="申请上公司")
    await session.flush()
    assert pr.status == "pending"
    # alice（非 admin）不能审批公司 KB
    with pytest.raises(PermissionError):
        await promotion_service.approve(session, s["alice"], pr.id)
    # admin 能审批 → 页被复制到公司 KB
    await promotion_service.approve(session, s["admin"], pr.id)
    await session.flush()
    company_pages = {p.slug for p in await wiki_repo.list_by_kb(session, s["company"].id)}
    assert "想法" in company_pages
    refreshed = await promotion_service.get(session, pr.id)
    assert refreshed.status == "approved" and refreshed.reviewer_id == s["admin"].id


async def test_reviewable_filtered_by_write_permission(session, setup):
    s = setup
    await promotion_service.request_promotion(session, s["alice"], s["page"].id, s["company"].id)
    await session.flush()
    assert len(await promotion_service.list_reviewable(session, s["admin"])) == 1  # admin 可审公司
    assert await promotion_service.list_reviewable(session, s["alice"]) == []       # alice 不可审公司


async def test_cannot_request_unreadable_page(session, setup):
    s = setup
    # bob 看不到 alice 个人 KB 的页
    bob = await org_service.create_user(session, email="bob@x.com", password="pw123456",
                                        display_name="Bob", role="user")
    await session.flush()
    with pytest.raises(PermissionError):
        await promotion_service.request_promotion(session, bob, s["page"].id, s["company"].id)
```

- [ ] **Step 4：实现 `promotion_repo.py`**（create / get / list_pending / save）

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PromotionRequest


async def create(session, *, page_id, to_kb_id, requested_by, note=None) -> PromotionRequest:
    pr = PromotionRequest(page_id=page_id, to_kb_id=to_kb_id, requested_by=requested_by, note=note)
    session.add(pr)
    return pr


async def get_by_id(session, pr_id) -> PromotionRequest | None:
    res = await session.execute(select(PromotionRequest).where(PromotionRequest.id == pr_id))
    return res.scalar_one_or_none()


async def list_pending(session) -> list[PromotionRequest]:
    res = await session.execute(
        select(PromotionRequest).where(PromotionRequest.status == "pending")
    )
    return list(res.scalars().all())
```

- [ ] **Step 5：实现 `promotion_service.py`（crown jewel：权限）**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromotionRequest, User
from app.repositories import kb_repo, promotion_repo, wiki_repo
from app.services import kb_service, permission_service


async def request_promotion(session, requester: User, page_id, to_kb_id, note=None) -> PromotionRequest:
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise LookupError("page not found")
    accessible = await permission_service.accessible_kb_ids(session, requester)
    if page.kb_id not in accessible:
        raise PermissionError("cannot promote a page you cannot read")
    if await kb_repo.get_by_id(session, to_kb_id) is None:
        raise LookupError("target kb not found")
    return await promotion_repo.create(
        session, page_id=page_id, to_kb_id=to_kb_id, requested_by=requester.id, note=note
    )


async def get(session, pr_id) -> PromotionRequest | None:
    return await promotion_repo.get_by_id(session, pr_id)


async def list_reviewable(session, reviewer: User) -> list[PromotionRequest]:
    out = []
    for pr in await promotion_repo.list_pending(session):
        kb = await kb_repo.get_by_id(session, pr.to_kb_id)
        if kb is not None and await permission_service.can_write(session, reviewer, kb):
            out.append(pr)
    return out


async def approve(session, reviewer: User, pr_id) -> PromotionRequest:
    pr = await promotion_repo.get_by_id(session, pr_id)
    if pr is None or pr.status != "pending":
        raise LookupError("request not found or already decided")
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    if kb is None or not await permission_service.can_write(session, reviewer, kb):
        raise PermissionError("no write permission on target kb")
    page = await wiki_repo.get_by_id(session, pr.page_id)
    if page is None:
        raise LookupError("source page gone")
    await wiki_repo.upsert(
        session, kb_id=pr.to_kb_id, slug=page.slug, title=page.title, page_type=page.page_type,
        content_md=page.content_md, frontmatter={**(page.frontmatter or {}), "promoted_from": str(page.kb_id)},
        source_ids=list(page.source_ids or []),
    )
    await session.flush()
    await kb_service.rebuild_index(session, pr.to_kb_id)
    pr.status = "approved"
    pr.reviewer_id = reviewer.id
    pr.decided_at = datetime.now(timezone.utc)
    return pr


async def reject(session, reviewer: User, pr_id, note=None) -> PromotionRequest:
    pr = await promotion_repo.get_by_id(session, pr_id)
    if pr is None or pr.status != "pending":
        raise LookupError("request not found or already decided")
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    if kb is None or not await permission_service.can_write(session, reviewer, kb):
        raise PermissionError("no write permission on target kb")
    pr.status = "rejected"
    pr.reviewer_id = reviewer.id
    pr.note = note or pr.note
    pr.decided_at = datetime.now(timezone.utc)
    return pr
```

- [ ] **Step 6：跑 `tests/test_promotion_service.py` + `tests/test_ingest_service.py` PASS。提交。**

```bash
git commit -m "feat(promotion): promotion_service（申请/审核队列/批准复制/拒绝，权限正确）+ kb_service.rebuild_index 抽取"
```

---

### Task 3：schemas + controllers + 路由 + API 测试

**Files:** 新增 `api/app/schemas/promotion.py`、`api/app/controllers/reviews.py`；改 `api/app/main.py`；测试 `api/tests/test_api_reviews.py`

- [ ] **Step 1：`schemas/promotion.py`**

```python
import uuid
from pydantic import BaseModel


class PromotionCreate(BaseModel):
    to_kb_id: uuid.UUID
    note: str | None = None


class ReviewDecision(BaseModel):
    note: str | None = None


class PromotionOut(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    page_title: str
    to_kb_id: uuid.UUID
    to_kb_name: str
    requested_by: uuid.UUID
    status: str
    note: str | None = None
```

- [ ] **Step 2：`controllers/reviews.py`**（promote 在 page 维度；reviews 队列 + approve/reject）

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import kb_repo, wiki_repo
from app.schemas.promotion import PromotionCreate, PromotionOut, ReviewDecision
from app.services import promotion_service

router = APIRouter(tags=["reviews"])


async def _to_out(session, pr) -> PromotionOut:
    page = await wiki_repo.get_by_id(session, pr.page_id)
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    return PromotionOut(
        id=pr.id, page_id=pr.page_id, page_title=page.title if page else "(已删除)",
        to_kb_id=pr.to_kb_id, to_kb_name=kb.name if kb else "(未知)",
        requested_by=pr.requested_by, status=pr.status, note=pr.note,
    )


@router.post("/pages/{page_id}/promote", response_model=PromotionOut)
async def promote(page_id: uuid.UUID, body: PromotionCreate,
                  user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        pr = await promotion_service.request_promotion(session, user, page_id, body.to_kb_id, note=body.note)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.get("/reviews", response_model=list[PromotionOut])
async def list_reviews(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    prs = await promotion_service.list_reviewable(session, user)
    return [await _to_out(session, pr) for pr in prs]


@router.post("/reviews/{pr_id}/approve", response_model=PromotionOut)
async def approve(pr_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        pr = await promotion_service.approve(session, user, pr_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.post("/reviews/{pr_id}/reject", response_model=PromotionOut)
async def reject(pr_id: uuid.UUID, body: ReviewDecision,
                 user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        pr = await promotion_service.reject(session, user, pr_id, note=body.note)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)
```

- [ ] **Step 3：`main.py` 注册** `reviews` 路由（`app.include_router(reviews.router, prefix="/api")`）。

- [ ] **Step 4：API 测试 `tests/test_api_reviews.py`**（端到端：alice 申请 → admin 队列见到 → 批准 → 公司 KB 出现该页；非授权 403）。用既有 `client`/`session` 夹具 + `app.dependency_overrides[get_current_user]` 切换身份。

- [ ] **Step 5：全量 `pytest` PASS。提交。**

```bash
git commit -m "feat(api): /pages/{id}/promote、/reviews 队列、approve/reject 端点"
```

---

### Task 4：前端审核界面

**Files:** 改 `web/src/api/types.ts`（PromotionOut）、`web/src/components/Layout.tsx`（审核入口）、`web/src/App.tsx`（/reviews 路由）、`web/src/pages/PageDetailPage.tsx`（申请晋升）；新增 `web/src/pages/ReviewsPage.tsx`

- [ ] **Step 1：types 加 `PromotionOut`**（id/page_id/page_title/to_kb_id/to_kb_name/requested_by/status/note）。
- [ ] **Step 2：`ReviewsPage.tsx`**：拉 `/reviews`，每条显示 page_title → to_kb_name，按钮 批准(`POST /reviews/{id}/approve`)/拒绝(`/reject`)，操作后刷新。
- [ ] **Step 3：`PageDetailPage.tsx`**：加"申请晋升"——选目标 KB（拉 `/kbs`）+ `POST /pages/{id}/promote`，反馈结果。
- [ ] **Step 4：`Layout.tsx` 加"审核"入口**（所有登录用户可见；后端按 can_write 过滤队列，无可审则空）。`App.tsx` 加 `/reviews` 路由。
- [ ] **Step 5：`pnpm build`/`pnpm test` 通过。提交。**

```bash
git commit -m "feat(web): 审核队列页 + 页详情申请晋升"
```

---

### Task 5：docker 端到端验证

- [ ] 重建 api+web；脚本：admin 建 alice → alice 登录在其个人/可写 KB 建/已有页 → POST promote 到公司 KB → admin GET /reviews 见到 → approve → GET 公司 KB pages 含该页。

---

## Self-Review
- **权限不变量**：申请须 `page.kb_id ∈ accessible(requester)`；审批/队列须 `can_write(reviewer, to_kb)`（公司/部门→admin、团队→成员）。三条均有单测。✓
- **DRY**：index 重建抽到 `kb_service.rebuild_index`，ingest 与 promotion 共用。✓
- **CLAUDE.md**：迁移用 `alembic revision` 生成。✓
- **可观测/可追溯**：晋升页 frontmatter 记 `promoted_from`；request 记 reviewer_id/decided_at。✓
- **未含（后续）**：晋升历史页、批量审核、撤销晋升、通知。

## 执行交接
按 executing-plans 逐 Task 实现，后端 TDD、前端 build 通过即提交，最后 docker e2e。

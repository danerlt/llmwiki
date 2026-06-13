# 子计划 8：审计日志 / 活动轨迹 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。后端 TDD，前端 build 通过即提交。迁移用 `alembic revision` 生成。

**Goal（企业治理/合规）:** 记录关键动作的不可变审计事件——谁(actor)、何时(created_at)、做了什么(action)、对象(target)、上下文(detail)。覆盖：晋升申请/批准/拒绝、建用户/部门/团队、源上传。提供 `GET /api/audit`(仅 admin) 与前端审计页。

**Architecture:** `AuditEvent` 模型 + `audit_repo` + `audit_service.record/list_recent`；审计在**控制器边界**记录（控制器持有 current_user=actor，服务层保持纯净）；与业务变更同事务提交（动作成功才留痕）。

**Tech Stack:** 同前。

**Definition of Done:** ①后端 `pytest` 全绿（记录 + admin-only 列表 + 非 admin 403 + 晋升/建用户等动作产生事件）；②前端 build 绿，admin 可见"审计"页列出最近事件；③docker：admin 建用户后 `/api/audit` 出现 `user.create` 事件。

---

### Task 1：模型 + 迁移 0006（audit_events）

- 新增 `app/models/audit_event.py`：`AuditEvent(id, actor_id→users, action str(64), target_type str(32) null, target_id Uuid null, detail JSON null, created_at)`；注册 `models/__init__`。
- 测试 `tests/test_audit_model.py`：持久化一条事件。
- `alembic revision -m "audit events"` 生成骨架，填建表（含 `ix_audit_events_created_at` 索引）。`alembic history` 确认链。
- 提交：`feat(model): audit_events 模型 + 迁移 0006`

```python
# app/models/audit_event.py
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

---

### Task 2：audit_repo + audit_service（TDD）

- `app/repositories/audit_repo.py`：`create(session, *, actor_id, action, target_type, target_id, detail)`、`list_recent(session, limit=100)`（按 created_at desc）。
- `app/services/audit_service.py`：`record(session, *, actor_id, action, target_type=None, target_id=None, detail=None)`（调 repo.create，不 commit）、`list_recent(session, limit=100)`。
- 测试 `tests/test_audit_service.py`：record 后 list_recent 含该事件、按时间倒序。
- 提交：`feat(audit): audit_repo + audit_service（record/list_recent）`

```python
# repositories/audit_repo.py
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditEvent


async def create(session, *, actor_id, action, target_type=None, target_id=None, detail=None) -> AuditEvent:
    ev = AuditEvent(actor_id=actor_id, action=action, target_type=target_type,
                    target_id=target_id, detail=detail)
    session.add(ev)
    return ev


async def list_recent(session, limit: int = 100) -> list[AuditEvent]:
    res = await session.execute(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit))
    return list(res.scalars().all())
```

```python
# services/audit_service.py
from app.repositories import audit_repo


async def record(session, *, actor_id, action, target_type=None, target_id=None, detail=None):
    return await audit_repo.create(session, actor_id=actor_id, action=action,
                                   target_type=target_type, target_id=target_id, detail=detail)


async def list_recent(session, limit: int = 100):
    return await audit_repo.list_recent(session, limit)
```

---

### Task 3：在控制器埋点 + GET /api/audit + API 测试

- 在控制器边界（持有 current_user）成功动作后、commit 前调 `audit_service.record`：
  - `controllers/reviews.py`：promote→`promotion.request`、approve→`promotion.approve`、reject→`promotion.reject`（target_type="page"/"promotion"，detail 含 to_kb_id）。
  - `controllers/org.py`：create_user→`user.create`、create_department→`department.create`、create_team→`team.create`、add_member→`team.add_member`。
  - `controllers/sources.py`：upload→`source.upload`（target_type="source", target_id=src.id, detail={"kb_id":...,"filename":...}）。
- `controllers/audit.py`（新）：`GET /api/audit`，`dependencies=[Depends(require_admin)]`，返回 `list_recent` 富化 actor_email。
- `schemas/audit.py`：`AuditEventOut(id, actor_id, actor_email, action, target_type, target_id, detail, created_at)`。
- `main.py` 注册 audit 路由。
- 测试 `tests/test_api_audit.py`：admin 建用户后 `GET /api/audit` 含 `user.create`；非 admin 访问 `/api/audit` → 403。
- 提交：`feat(api): 关键动作审计埋点 + GET /api/audit（admin）`

```python
# schemas/audit.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str
    action: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    detail: dict | None = None
    created_at: datetime
```

```python
# controllers/audit.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import user_repo
from app.schemas.audit import AuditEventOut
from app.services import audit_service

router = APIRouter(tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/audit", response_model=list[AuditEventOut])
async def list_audit(session: AsyncSession = Depends(get_db)):
    out = []
    for ev in await audit_service.list_recent(session, limit=100):
        actor = await user_repo.get_by_id(session, ev.actor_id)
        out.append(AuditEventOut(
            id=ev.id, actor_id=ev.actor_id, actor_email=actor.email if actor else "(未知)",
            action=ev.action, target_type=ev.target_type, target_id=ev.target_id,
            detail=ev.detail, created_at=ev.created_at,
        ))
    return out
```

> 埋点示例（reviews.py promote 内 commit 前）：
> `await audit_service.record(session, actor_id=user.id, action="promotion.request", target_type="page", target_id=page_id, detail={"to_kb_id": str(body.to_kb_id)})`

---

### Task 4：前端审计页（admin）

- `api/types.ts` 加 `AuditEventOut`。
- `pages/AuditPage.tsx`：拉 `/audit`，表格列 时间 / actor_email / action / target_type，detail 折叠。
- `Layout.tsx`：admin 可见"审计"入口；`App.tsx` 加 `/audit` 路由。
- `pnpm build`/`test` 绿。提交：`feat(web): 审计日志页（admin）`

---

### Task 5：docker e2e

- 重建 api+web；admin 建一个用户 → `GET /api/audit` 含 `user.create`；非 admin 403。

---

## Self-Review
- **不可变留痕**：仅追加，无更新/删除端点。✓
- **与动作同事务**：record 在 commit 前调用，动作回滚则事件也不留（一致）。✓
- **权限**：`/api/audit` require_admin；埋点 actor 取自 current_user。✓
- **服务层纯净**：审计在控制器边界，不污染 service 签名。✓
- **未含（后续）**：分页/筛选/导出、保留期、对读操作审计。

## 执行交接
按 executing-plans 逐 Task，后端 TDD、前端 build 通过即提交，最后 docker e2e。

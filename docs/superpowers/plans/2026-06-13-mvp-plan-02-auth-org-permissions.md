# 子计划 2：认证 · 组织 · 权限 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。每步先写失败测试→看失败→最小实现→看通过。git 由用户管理，子代理不 commit。

**Goal:** 实现 JWT 登录、组织结构（部门多级树 / 跨部门团队 / 用户）、四类 KB 供给，以及核心 `permission_service`（可见 KB 集合 + 写权限），并用 TDD 锁死权限隔离不变量。

**Architecture:** Controller–Service–Repository 分层。权限读写逻辑集中在 `services/permission_service.py`，用真实 DB（测试用 SQLite 内存库，生产 Postgres）验证。所有查询走 repository 层。

**Tech Stack:** FastAPI、SQLAlchemy 2.0(async)、bcrypt、python-jose(JWT)、pytest+aiosqlite。

**Definition of Done:** `pytest` 全绿（含权限隔离用例：下级部门不串平级、非成员不见团队 KB、个人 KB 仅本人）；登录→/me→建组织→列 KB 端到端通过；alembic 0002 迁移脚本就位。

**测试基础设施决策:** 单元/集成测试用 `sqlite+aiosqlite:///:memory:`（StaticPool 单连接共享）。模型仅用 Uuid/FK/递归 CTE，SQLite 与 Postgres 行为一致。Postgres 专属特性（tsvector/trgm）在子计划 4 才出现。

---

## 文件结构（本计划产出/修改）

```
api/
  requirements.txt                    # 修改：加 bcrypt、aiosqlite；移除 passlib
  app/
    models/__init__.py user.py department.py team.py knowledge_base.py   # 新增
    core/security.py                  # 新增：bcrypt + JWT
    core/deps.py                      # 新增：get_current_user / require_admin
    repositories/__init__.py base.py user_repo.py org_repo.py kb_repo.py  # 新增
    services/permission_service.py    # 新增：核心
    services/kb_service.py            # 新增：KB 供给
    services/auth_service.py services/org_service.py                      # 新增
    schemas/auth.py schemas/org.py schemas/kb.py                          # 新增
    controllers/auth.py controllers/org.py controllers/kb.py             # 新增
    main.py                           # 修改：注册新路由
  migrations/versions/0002_org_kb.py  # 新增
  scripts/seed.py                     # 新增
  tests/
    conftest.py                       # 修改：加 sqlite session + client fixture
    test_security.py test_permissions.py test_repositories.py
    test_api_auth.py test_api_org.py test_kb_listing.py                  # 新增
```

---

### Task 1：依赖 + ORM 模型 + 测试夹具

**Files:** 修改 `api/requirements.txt`、`api/tests/conftest.py`；新增 `api/app/models/*`；测试 `api/tests/test_models.py`

- [ ] **Step 1：改 `requirements.txt`** —— 删除 `passlib[bcrypt]>=1.7` 行，新增：
```
bcrypt>=4.1
aiosqlite>=0.20
```
然后 `pip install --break-system-packages -q -r requirements.txt`。

- [ ] **Step 2：写失败测试 `tests/test_models.py`**
```python
import uuid

from app.models import Department, KnowledgeBase, Team, User, UserTeam


async def test_models_persist(session):
    d = Department(name="技术部")
    session.add(d)
    await session.flush()
    u = User(email="a@x.com", password_hash="h", display_name="Alice", role="user", department_id=d.id)
    session.add(u)
    await session.flush()
    kb = KnowledgeBase(scope_type="department", scope_ref_id=d.id, name="技术部 KB")
    session.add(kb)
    await session.flush()
    assert isinstance(u.id, uuid.UUID)
    assert u.department_id == d.id
    assert kb.scope_type == "department"
```

- [ ] **Step 3：写 `tests/conftest.py`（覆盖原占位）**
```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401  注册所有模型到 Base.metadata


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()
```

- [ ] **Step 4：建模型文件**

`app/models/department.py`:
```python
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id"), nullable=True
    )
```

`app/models/user.py`:
```python
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id"), nullable=True
    )
```

`app/models/team.py`:
```python
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))


class UserTeam(Base):
    __tablename__ = "user_teams"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    team_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("teams.id"), primary_key=True)
```

`app/models/knowledge_base.py`:
```python
import uuid

from sqlalchemy import String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("scope_type", "scope_ref_id", name="uq_kb_scope"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scope_type: Mapped[str] = mapped_column(String(16))  # company|department|team|personal
    scope_ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
```

`app/models/__init__.py`:
```python
from app.models.department import Department
from app.models.knowledge_base import KnowledgeBase
from app.models.team import Team, UserTeam
from app.models.user import User

__all__ = ["Department", "KnowledgeBase", "Team", "UserTeam", "User"]
```

- [ ] **Step 5：跑测试** `python -m pytest tests/test_models.py -q -p no:cacheprovider --basetemp=/tmp/pytest_tmp` → PASS。

---

### Task 2：安全模块 security.py（bcrypt + JWT）

**Files:** 新增 `api/app/core/security.py`；测试 `api/tests/test_security.py`

- [ ] **Step 1：写失败测试 `tests/test_security.py`**
```python
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token("user-id-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
```

- [ ] **Step 2：实现 `app/core/security.py`**
```python
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(subject: str, expires_min: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_min or settings.jwt_expire_min
    )
    return jwt.encode({"sub": subject, "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
```

- [ ] **Step 3：跑测试** → PASS。

---

### Task 3：迁移 0002（org + kb 表）

**Files:** 新增 `api/migrations/versions/0002_org_kb.py`

- [ ] **Step 1：写迁移**
```python
"""org and kb tables

Revision ID: 0002_org_kb
Revises: 0001_baseline
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_org_kb"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("departments.id"), nullable=True),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id"), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "user_teams",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), primary_key=True),
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("scope_ref_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("scope_type", "scope_ref_id", name="uq_kb_scope"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_bases")
    op.drop_table("user_teams")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("teams")
    op.drop_table("departments")
```

- [ ] **Step 2：验证脚本可识别** `python -m alembic history` → 列出 `0001_baseline -> 0002_org_kb (head)`。

---

### Task 4：仓储层 repositories（SQLite TDD）

**Files:** 新增 `api/app/repositories/{__init__.py,base.py,user_repo.py,org_repo.py,kb_repo.py}`；测试 `api/tests/test_repositories.py`

- [ ] **Step 1：写失败测试 `tests/test_repositories.py`**
```python
from app.repositories import kb_repo, org_repo, user_repo


async def test_user_repo_get_by_email(session):
    u = await user_repo.create(session, email="a@x.com", password_hash="h", display_name="A", role="user", department_id=None)
    await session.flush()
    found = await user_repo.get_by_email(session, "a@x.com")
    assert found is not None and found.id == u.id
    assert await user_repo.get_by_email(session, "none@x.com") is None


async def test_org_repo_department_tree(session):
    root = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    child = await org_repo.create_department(session, name="后端组", parent_id=root.id)
    await session.flush()
    anc = await org_repo.ancestor_department_ids(session, child.id)
    assert set(anc) == {root.id, child.id}


async def test_kb_repo_create_and_list(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司 KB")
    await session.flush()
    rows = await kb_repo.list_by_scope(session, "company", None)
    assert kb.id in [r.id for r in rows]
```

- [ ] **Step 2：实现 `app/repositories/__init__.py`** → 空 `# package`。

- [ ] **Step 3：实现 `app/repositories/user_repo.py`**
```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def create(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    display_name: str,
    role: str = "user",
    department_id: uuid.UUID | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
        department_id=department_id,
    )
    session.add(user)
    return user


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    res = await session.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def team_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    from app.models import UserTeam

    res = await session.execute(select(UserTeam.team_id).where(UserTeam.user_id == user_id))
    return [r[0] for r in res.all()]
```

- [ ] **Step 4：实现 `app/repositories/org_repo.py`**
```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Team, UserTeam


async def create_department(
    session: AsyncSession, *, name: str, parent_id: uuid.UUID | None
) -> Department:
    dept = Department(name=name, parent_id=parent_id)
    session.add(dept)
    return dept


async def list_departments(session: AsyncSession) -> list[Department]:
    res = await session.execute(select(Department))
    return list(res.scalars().all())


async def create_team(session: AsyncSession, *, name: str) -> Team:
    team = Team(name=name)
    session.add(team)
    return team


async def add_team_member(session: AsyncSession, *, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session.add(UserTeam(team_id=team_id, user_id=user_id))


async def ancestor_department_ids(
    session: AsyncSession, dept_id: uuid.UUID | None
) -> list[uuid.UUID]:
    """返回 dept_id 自身 + 所有祖先部门 id（向上 walk parent_id）。"""
    if dept_id is None:
        return []
    dept = Department.__table__
    base = (
        select(dept.c.id, dept.c.parent_id)
        .where(dept.c.id == dept_id)
        .cte("anc", recursive=True)
    )
    parent = dept.alias()
    rec = select(parent.c.id, parent.c.parent_id).join(base, parent.c.id == base.c.parent_id)
    anc = base.union_all(rec)
    res = await session.execute(select(anc.c.id))
    return [r[0] for r in res.all()]
```

- [ ] **Step 5：实现 `app/repositories/kb_repo.py`**
```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase


async def create(
    session: AsyncSession, *, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
) -> KnowledgeBase:
    kb = KnowledgeBase(scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)
    session.add(kb)
    return kb


async def list_by_scope(
    session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None
) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.scope_type == scope_type)
    stmt = stmt.where(
        KnowledgeBase.scope_ref_id == scope_ref_id
        if scope_ref_id is not None
        else KnowledgeBase.scope_ref_id.is_(None)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def list_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[KnowledgeBase]:
    if not ids:
        return []
    res = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(ids)))
    return list(res.scalars().all())
```

- [ ] **Step 6：跑测试** → PASS。

---

### Task 5：permission_service（核心）+ kb_service 供给

**Files:** 新增 `api/app/services/__init__.py`、`api/app/services/permission_service.py`、`api/app/services/kb_service.py`；测试 `api/tests/test_permissions.py`

- [ ] **Step 1：写失败测试 `tests/test_permissions.py`（隔离不变量，crown jewel）**
```python
import pytest_asyncio

from app.repositories import kb_repo, org_repo, user_repo
from app.services import kb_service, permission_service


@pytest_asyncio.fixture
async def org(session):
    """构造组织：
    部门树：技术部 > {后端组, 前端组}；产品部
    团队：项目X（跨部门）
    用户：admin / alice(后端组) / bob(前端组) / carol(产品部)
    KB：company、各部门 KB、项目X KB、各人 personal KB
    alice、carol 加入 项目X
    """
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    product = await org_repo.create_department(session, name="产品部", parent_id=None)
    await session.flush()

    projx = await org_repo.create_team(session, name="项目X")
    await session.flush()

    admin = await user_repo.create(session, email="admin@x.com", password_hash="h", display_name="Admin", role="admin", department_id=tech.id)
    alice = await user_repo.create(session, email="alice@x.com", password_hash="h", display_name="Alice", role="user", department_id=backend.id)
    bob = await user_repo.create(session, email="bob@x.com", password_hash="h", display_name="Bob", role="user", department_id=frontend.id)
    carol = await user_repo.create(session, email="carol@x.com", password_hash="h", display_name="Carol", role="user", department_id=product.id)
    await session.flush()

    await org_repo.add_team_member(session, team_id=projx.id, user_id=alice.id)
    await org_repo.add_team_member(session, team_id=projx.id, user_id=carol.id)

    company_kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await kb_service.ensure_kb(session, "department", tech.id, "技术部")
    await kb_service.ensure_kb(session, "department", backend.id, "后端组")
    await kb_service.ensure_kb(session, "department", frontend.id, "前端组")
    await kb_service.ensure_kb(session, "department", product.id, "产品部")
    await kb_service.ensure_kb(session, "team", projx.id, "项目X")
    for u in (admin, alice, bob, carol):
        await kb_service.ensure_kb(session, "personal", u.id, f"{u.display_name} 个人")
    await session.flush()

    return {
        "tech": tech, "backend": backend, "frontend": frontend, "product": product,
        "projx": projx, "admin": admin, "alice": alice, "bob": bob, "carol": carol,
        "company_kb": company_kb,
    }


async def _kb_names(session, ids):
    rows = await kb_repo.list_by_ids(session, list(ids))
    return {r.name for r in rows}


async def test_alice_sees_ancestors_and_team_not_siblings(session, org):
    ids = await permission_service.accessible_kb_ids(session, org["alice"])
    names = await _kb_names(session, ids)
    assert names == {"公司", "技术部", "后端组", "项目X", "Alice 个人"}
    assert "前端组" not in names   # 平级部门看不到
    assert "Bob 个人" not in names  # 他人个人看不到
    assert "产品部" not in names


async def test_bob_not_in_team_cannot_see_team_kb(session, org):
    ids = await permission_service.accessible_kb_ids(session, org["bob"])
    names = await _kb_names(session, ids)
    assert names == {"公司", "技术部", "前端组", "Bob 个人"}
    assert "项目X" not in names      # 非团队成员
    assert "后端组" not in names


async def test_can_write_rules(session, org):
    company_kb = org["company_kb"]
    tech_kb = (await kb_repo.list_by_scope(session, "department", org["tech"].id))[0]
    projx_kb = (await kb_repo.list_by_scope(session, "team", org["projx"].id))[0]
    alice_kb = (await kb_repo.list_by_scope(session, "personal", org["alice"].id))[0]
    bob_kb = (await kb_repo.list_by_scope(session, "personal", org["bob"].id))[0]

    assert await permission_service.can_write(session, org["admin"], company_kb) is True
    assert await permission_service.can_write(session, org["admin"], tech_kb) is True
    assert await permission_service.can_write(session, org["alice"], tech_kb) is False  # 非 admin
    assert await permission_service.can_write(session, org["alice"], alice_kb) is True   # 本人
    assert await permission_service.can_write(session, org["alice"], projx_kb) is True   # 团队成员
    assert await permission_service.can_write(session, org["alice"], bob_kb) is False    # 他人个人
```

- [ ] **Step 2：实现 `app/services/__init__.py`** → `# package`。

- [ ] **Step 3：实现 `app/services/kb_service.py`**
```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase
from app.repositories import kb_repo


async def ensure_kb(
    session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
) -> KnowledgeBase:
    """若该作用域 KB 已存在则返回，否则创建。"""
    existing = await kb_repo.list_by_scope(session, scope_type, scope_ref_id)
    if existing:
        return existing[0]
    return await kb_repo.create(session, scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)
```

- [ ] **Step 4：实现 `app/services/permission_service.py`**
```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, User, UserTeam
from app.repositories import org_repo


async def accessible_kb_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    """用户可读的 KB 集合 = 公司 ∪ 本部门及所有祖先 ∪ 所加入团队 ∪ 个人。"""
    ids: set[uuid.UUID] = set()

    # company
    res = await session.execute(
        select(KnowledgeBase.id).where(KnowledgeBase.scope_type == "company")
    )
    ids.update(r[0] for r in res.all())

    # department + ancestors
    anc = await org_repo.ancestor_department_ids(session, user.department_id)
    if anc:
        res = await session.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.scope_type == "department",
                KnowledgeBase.scope_ref_id.in_(anc),
            )
        )
        ids.update(r[0] for r in res.all())

    # teams
    res = await session.execute(select(UserTeam.team_id).where(UserTeam.user_id == user.id))
    team_ids = [r[0] for r in res.all()]
    if team_ids:
        res = await session.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.scope_type == "team",
                KnowledgeBase.scope_ref_id.in_(team_ids),
            )
        )
        ids.update(r[0] for r in res.all())

    # personal
    res = await session.execute(
        select(KnowledgeBase.id).where(
            KnowledgeBase.scope_type == "personal",
            KnowledgeBase.scope_ref_id == user.id,
        )
    )
    ids.update(r[0] for r in res.all())

    return ids


async def can_write(session: AsyncSession, user: User, kb: KnowledgeBase) -> bool:
    if kb.scope_type == "personal":
        return kb.scope_ref_id == user.id
    if kb.scope_type == "team":
        res = await session.execute(
            select(UserTeam).where(
                UserTeam.user_id == user.id, UserTeam.team_id == kb.scope_ref_id
            )
        )
        return res.first() is not None
    if kb.scope_type in ("department", "company"):
        return user.role == "admin"
    return False
```

- [ ] **Step 5：跑测试** `python -m pytest tests/test_permissions.py -q -p no:cacheprovider --basetemp=/tmp/pytest_tmp` → PASS。**这是本计划最关键的门槛。**

---

### Task 6：auth_service / org_service + schemas + deps

**Files:** 新增 `api/app/services/auth_service.py`、`api/app/services/org_service.py`、`api/app/schemas/{auth,org,kb}.py`、`api/app/core/deps.py`

- [ ] **Step 1：实现 `app/schemas/auth.py`**
```python
import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    department_id: uuid.UUID | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2：实现 `app/schemas/org.py`**
```python
import uuid

from pydantic import BaseModel, EmailStr


class DepartmentCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    role: str = "user"
    department_id: uuid.UUID | None = None


class TeamMemberAdd(BaseModel):
    user_id: uuid.UUID
```

- [ ] **Step 3：实现 `app/schemas/kb.py`**
```python
import uuid

from pydantic import BaseModel


class KBOut(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_ref_id: uuid.UUID | None
    name: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 4：实现 `app/services/auth_service.py`**
```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.repositories import user_repo


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await user_repo.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
```

- [ ] **Step 5：实现 `app/services/org_service.py`**
```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Department, Team, User
from app.repositories import org_repo, user_repo
from app.services import kb_service


async def create_department(session: AsyncSession, *, name: str, parent_id: uuid.UUID | None) -> Department:
    dept = await org_repo.create_department(session, name=name, parent_id=parent_id)
    await session.flush()
    await kb_service.ensure_kb(session, "department", dept.id, name)
    return dept


async def create_team(session: AsyncSession, *, name: str) -> Team:
    team = await org_repo.create_team(session, name=name)
    await session.flush()
    await kb_service.ensure_kb(session, "team", team.id, name)
    return team


async def create_user(
    session: AsyncSession, *, email: str, password: str, display_name: str,
    role: str = "user", department_id: uuid.UUID | None = None,
) -> User:
    user = await user_repo.create(
        session, email=email, password_hash=hash_password(password),
        display_name=display_name, role=role, department_id=department_id,
    )
    await session.flush()
    await kb_service.ensure_kb(session, "personal", user.id, f"{display_name} 个人")
    return user
```

- [ ] **Step 6：实现 `app/core/deps.py`**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User
from app.repositories import user_repo

bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(creds.credentials)
        user_id = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    import uuid

    user = await user_repo.get_by_id(session, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user
```

- [ ] **Step 7：无独立单测（由 Task 7 的 API 测试覆盖）。确保 `python -m pytest -q` 仍全绿。**

---

### Task 7：controllers + 路由装配 + seed + API 测试

**Files:** 新增 `api/app/controllers/{auth,org,kb}.py`、`api/scripts/seed.py`；修改 `api/app/main.py`；测试 `api/tests/{test_api_auth,test_api_org,test_kb_listing}.py`

- [ ] **Step 1：实现 `app/controllers/auth.py`**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
```

- [ ] **Step 2：实现 `app/controllers/org.py`**
```python
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import org_repo
from app.schemas.org import (
    DepartmentCreate, DepartmentOut, TeamCreate, TeamMemberAdd, TeamOut, UserCreate,
)
from app.schemas.auth import UserOut
from app.services import org_service

router = APIRouter(tags=["org"], dependencies=[Depends(require_admin)])


@router.post("/departments", response_model=DepartmentOut)
async def create_department(body: DepartmentCreate, session: AsyncSession = Depends(get_db)):
    dept = await org_service.create_department(session, name=body.name, parent_id=body.parent_id)
    await session.commit()
    return dept


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(session: AsyncSession = Depends(get_db)):
    return await org_repo.list_departments(session)


@router.post("/teams", response_model=TeamOut)
async def create_team(body: TeamCreate, session: AsyncSession = Depends(get_db)):
    team = await org_service.create_team(session, name=body.name)
    await session.commit()
    return team


@router.post("/teams/{team_id}/members")
async def add_member(team_id: uuid.UUID, body: TeamMemberAdd, session: AsyncSession = Depends(get_db)):
    await org_repo.add_team_member(session, team_id=team_id, user_id=body.user_id)
    await session.commit()
    return {"status": "ok"}


@router.post("/users", response_model=UserOut)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_db)):
    user = await org_service.create_user(
        session, email=body.email, password=body.password, display_name=body.display_name,
        role=body.role, department_id=body.department_id,
    )
    await session.commit()
    return user
```

- [ ] **Step 3：实现 `app/controllers/kb.py`**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import kb_repo
from app.schemas.kb import KBOut
from app.services import permission_service

router = APIRouter(tags=["kb"])


@router.get("/kbs", response_model=list[KBOut])
async def list_my_kbs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    ids = await permission_service.accessible_kb_ids(session, user)
    return await kb_repo.list_by_ids(session, list(ids))
```

- [ ] **Step 4：改 `app/main.py` 注册路由**
```python
from fastapi import FastAPI

from app.controllers import auth, health, kb, org


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Wiki API")
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(org.router, prefix="/api")
    app.include_router(kb.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 5：在 `tests/conftest.py` 追加 `client` 夹具（覆盖 get_db 用测试库）**
```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 6：写 API 测试 `tests/test_api_auth.py`**
```python
from app.services import org_service


async def test_login_and_me(client, session):
    await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin",
    )
    await session.commit()

    r = await client.post("/api/auth/login", json={"email": "admin@x.com", "password": "pw123456"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == "admin@x.com"


async def test_login_bad_password(client, session):
    await org_service.create_user(session, email="u@x.com", password="right1", display_name="U")
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": "u@x.com", "password": "wrong1"})
    assert r.status_code == 401
```

- [ ] **Step 7：写 API 测试 `tests/test_api_org.py`（admin 鉴权）**
```python
from app.services import org_service


async def _token(client, session, role):
    await org_service.create_user(session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role)
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": f"{role}@x.com", "password": "pw123456"})
    return r.json()["access_token"]


async def test_admin_can_create_department(client, session):
    token = await _token(client, session, "admin")
    r = await client.post("/api/departments", json={"name": "技术部"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "技术部"


async def test_non_admin_forbidden(client, session):
    token = await _token(client, session, "user")
    r = await client.post("/api/departments", json={"name": "X"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
```

- [ ] **Step 8：写 API 测试 `tests/test_kb_listing.py`（权限过滤）**
```python
from app.repositories import org_repo
from app.services import kb_service, org_service


async def test_kb_listing_filtered_by_permission(client, session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    await kb_service.ensure_kb(session, "company", None, "公司")
    await kb_service.ensure_kb(session, "department", tech.id, "技术部")
    await kb_service.ensure_kb(session, "department", backend.id, "后端组")
    await kb_service.ensure_kb(session, "department", frontend.id, "前端组")
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id,
    )
    await session.commit()

    r = await client.post("/api/auth/login", json={"email": "alice@x.com", "password": "pw123456"})
    token = r.json()["access_token"]
    r2 = await client.get("/api/kbs", headers={"Authorization": f"Bearer {token}"})
    names = {kb["name"] for kb in r2.json()}
    assert names == {"公司", "技术部", "后端组", "Alice 个人"}
    assert "前端组" not in names
```

- [ ] **Step 9：实现 `scripts/seed.py`（初始化 admin + 样例组织）**
```python
import asyncio

from app.db.session import SessionLocal
from app.repositories import org_repo, user_repo
from app.services import kb_service, org_service


async def seed() -> None:
    async with SessionLocal() as session:
        if await user_repo.get_by_email(session, "admin@llmwiki.local"):
            print("already seeded")
            return
        await kb_service.ensure_kb(session, "company", None, "公司")
        tech = await org_service.create_department(session, name="技术部", parent_id=None)
        backend = await org_service.create_department(session, name="后端组", parent_id=tech.id)
        await org_service.create_department(session, name="前端组", parent_id=tech.id)
        await org_service.create_user(
            session, email="admin@llmwiki.local", password="admin12345",
            display_name="管理员", role="admin", department_id=tech.id,
        )
        await org_service.create_user(
            session, email="alice@llmwiki.local", password="alice12345",
            display_name="Alice", role="user", department_id=backend.id,
        )
        await session.commit()
        print("seeded: admin@llmwiki.local / admin12345")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 10：跑全量测试** `cd api && python -m pytest -q -p no:cacheprovider --basetemp=/tmp/pytest_tmp` → 全绿（含子计划1 的 4 个 + 本计划新增）。

---

## Self-Review（计划自检）

- **Spec 覆盖**：覆盖 spec 第 5（users/departments/teams/user_teams/knowledge_bases 模型）、第 6（accessible_kb_ids/can_write + 铁律：检索按可见 KB 过滤，本计划在 `/api/kbs` 落地）、第 10（auth/me/org/kbs 端点）、第 12（分层）。sources/wiki_pages/page_links 与检索属子计划 3/4。✓
- **占位符扫描**：无 TODO；每步完整代码。✓
- **类型/命名一致**：`org_repo.ancestor_department_ids`、`kb_repo.list_by_scope/list_by_ids`、`kb_service.ensure_kb(session, scope_type, scope_ref_id, name)`、`permission_service.accessible_kb_ids/can_write` 在 Task 4/5/6/7 引用一致。✓
- **依赖顺序**：models→security→migration→repos→permission→services→controllers 单向无环。✓
- **注意**：所有写端点在 controller 内 `await session.commit()`；测试用 SQLite，`Uuid`/递归 CTE 均可移植。

## 执行交接

按既定方式（subagent-driven）分 3 个实现子代理执行：①Task1-3（模型/安全/迁移）②Task4-5（仓储/权限，crown jewel）③Task6-7（服务/控制器/seed/API 测试），每组后做评审。

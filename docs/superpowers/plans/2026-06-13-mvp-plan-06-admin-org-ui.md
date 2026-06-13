# 子计划 6：管理员组织管理界面 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。每个 Task 跑通后立即提交。后端补两个列表端点（TDD），前端加 admin 界面（build/test 通过即可）。

**Goal:** 补齐 MVP 仅剩的功能缺口（spec §2.1 第 2 项组织结构管理）——后端补 `GET /teams`、`GET /users` 列表端点，前端加 **仅 admin 可见** 的管理界面：建/列 部门（多级，选父部门）、建/列 团队 + 加成员、建/列 用户（邮箱/密码/姓名/角色/部门）。

**Architecture:** 沿用既有分层与前端模式。org 路由已整体挂 `require_admin`，新端点天然仅 admin。前端新增 `AdminPage`，复用 `apiFetch/postJson`；`Layout` 按 `user.role==="admin"` 显示入口；`/admin` 路由。

**Tech Stack:** 同子计划 2/5。

**Definition of Done:** ①后端 `pytest` 全绿（新增 GET /teams、GET /users 用例，含非 admin 403）；②前端 `pnpm build`/`pnpm test` 通过；③admin 登录后可在 `/admin` 建部门/团队/用户、加团队成员，非 admin 看不到入口且直接访问被后端 403。

---

### Task 1：后端列表端点 GET /teams、GET /users（TDD）

**Files:** 修改 `api/app/repositories/org_repo.py`、`api/app/repositories/user_repo.py`、`api/app/controllers/org.py`；测试 `api/tests/test_api_org.py`（追加）

- [ ] **Step 1：追加失败测试到 `tests/test_api_org.py`**

```python
async def test_admin_lists_teams_and_users(client, session):
    token = await _token(client, session, "admin")
    await client.post("/api/teams", json={"name": "项目X"}, headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/api/teams", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and any(t["name"] == "项目X" for t in r.json())
    r2 = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200 and any(u["role"] == "admin" for u in r2.json())


async def test_non_admin_cannot_list_users(client, session):
    token = await _token(client, session, "user")
    r = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
```

- [ ] **Step 2：运行确认失败**（GET /teams、/users 未定义 → 405/404）。

- [ ] **Step 3：`org_repo.py` 追加 `list_teams`**

```python
async def list_teams(session: AsyncSession) -> list[Team]:
    res = await session.execute(select(Team))
    return list(res.scalars().all())
```

- [ ] **Step 4：`user_repo.py` 追加 `list_all`**

```python
async def list_all(session: AsyncSession) -> list[User]:
    res = await session.execute(select(User))
    return list(res.scalars().all())
```

- [ ] **Step 5：`controllers/org.py` 追加两个 GET**（import 处补 `user_repo`、`from app.schemas.auth import UserOut` 已在）

```python
@router.get("/teams", response_model=list[TeamOut])
async def list_teams(session: AsyncSession = Depends(get_db)):
    return await org_repo.list_teams(session)


@router.get("/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_db)):
    return await user_repo.list_all(session)
```

`controllers/org.py` 顶部 import 改为：`from app.repositories import org_repo, user_repo`。

- [ ] **Step 6：运行确认通过；提交**

```bash
git add api/app/repositories/org_repo.py api/app/repositories/user_repo.py api/app/controllers/org.py api/tests/test_api_org.py
git commit -m "feat(api): GET /teams、GET /users 列表端点（admin）"
```

---

### Task 2：前端 admin 管理界面

**Files:** 修改 `web/src/api/types.ts`（加 Department/Team）、`web/src/components/Layout.tsx`（admin 入口）、`web/src/App.tsx`（/admin 路由）；新增 `web/src/pages/AdminPage.tsx`

- [ ] **Step 1：`api/types.ts` 追加**

```ts
export interface Department {
  id: string;
  name: string;
  parent_id: string | null;
}
export interface Team {
  id: string;
  name: string;
}
```

- [ ] **Step 2：新增 `web/src/pages/AdminPage.tsx`**（部门/团队/用户三块，列表 + 表单）

```tsx
import { useEffect, useState, type FormEvent } from "react";

import { apiFetch, postJson } from "../api/client";
import type { Department, Team, UserOut } from "../api/types";

export default function AdminPage() {
  const [depts, setDepts] = useState<Department[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<UserOut[]>([]);
  const [msg, setMsg] = useState("");

  function reload() {
    apiFetch<Department[]>("/departments").then(setDepts).catch(() => setMsg("加载部门失败"));
    apiFetch<Team[]>("/teams").then(setTeams).catch(() => {});
    apiFetch<UserOut[]>("/users").then(setUsers).catch(() => {});
  }
  useEffect(reload, []);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setMsg("");
    try {
      await fn();
      setMsg(ok);
      reload();
    } catch {
      setMsg("操作失败（需要 admin 权限或输入有误）");
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">组织管理</h1>
      {msg && <p className="text-sm text-slate-600">{msg}</p>}

      <DeptSection depts={depts} onCreate={(name, parent_id) =>
        run(() => postJson("/departments", { name, parent_id }), "部门已创建")} />

      <TeamSection teams={teams} users={users}
        onCreate={(name) => run(() => postJson("/teams", { name }), "团队已创建")}
        onAddMember={(teamId, userId) =>
          run(() => postJson(`/teams/${teamId}/members`, { user_id: userId }), "成员已加入")} />

      <UserSection users={users} depts={depts}
        onCreate={(body) => run(() => postJson("/users", body), "用户已创建")} />
    </div>
  );
}

function DeptSection({ depts, onCreate }: {
  depts: Department[]; onCreate: (name: string, parentId: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name) return;
    onCreate(name, parent || null);
    setName("");
  }
  return (
    <section className="rounded border bg-white p-4">
      <h2 className="mb-2 font-semibold">部门</h2>
      <ul className="mb-3 list-disc pl-5 text-sm text-slate-700">
        {depts.map((d) => (
          <li key={d.id}>{d.name}{d.parent_id ? "（子部门）" : ""}</li>
        ))}
      </ul>
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input className="rounded border px-2 py-1" value={name}
          onChange={(e) => setName(e.target.value)} placeholder="部门名" />
        <select className="rounded border px-2 py-1" value={parent}
          onChange={(e) => setParent(e.target.value)}>
          <option value="">（顶级部门）</option>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <button className="rounded bg-slate-800 px-3 text-white">新建部门</button>
      </form>
    </section>
  );
}

function TeamSection({ teams, users, onCreate, onAddMember }: {
  teams: Team[]; users: UserOut[];
  onCreate: (name: string) => void;
  onAddMember: (teamId: string, userId: string) => void;
}) {
  const [name, setName] = useState("");
  const [teamId, setTeamId] = useState("");
  const [userId, setUserId] = useState("");
  return (
    <section className="rounded border bg-white p-4">
      <h2 className="mb-2 font-semibold">团队</h2>
      <ul className="mb-3 list-disc pl-5 text-sm text-slate-700">
        {teams.map((t) => <li key={t.id}>{t.name}</li>)}
      </ul>
      <form onSubmit={(e) => { e.preventDefault(); if (name) { onCreate(name); setName(""); } }}
        className="mb-2 flex gap-2">
        <input className="rounded border px-2 py-1" value={name}
          onChange={(e) => setName(e.target.value)} placeholder="团队名" />
        <button className="rounded bg-slate-800 px-3 text-white">新建团队</button>
      </form>
      <form onSubmit={(e) => { e.preventDefault(); if (teamId && userId) onAddMember(teamId, userId); }}
        className="flex flex-wrap gap-2">
        <select className="rounded border px-2 py-1" value={teamId}
          onChange={(e) => setTeamId(e.target.value)}>
          <option value="">选团队</option>
          {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select className="rounded border px-2 py-1" value={userId}
          onChange={(e) => setUserId(e.target.value)}>
          <option value="">选用户</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
        </select>
        <button className="rounded border px-3">加入成员</button>
      </form>
    </section>
  );
}

interface NewUser {
  email: string;
  password: string;
  display_name: string;
  role: string;
  department_id: string | null;
}

function UserSection({ users, depts, onCreate }: {
  users: UserOut[]; depts: Department[]; onCreate: (body: NewUser) => void;
}) {
  const [f, setF] = useState<NewUser>({
    email: "", password: "", display_name: "", role: "user", department_id: null,
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!f.email || !f.password) return;
    onCreate(f);
    setF({ email: "", password: "", display_name: "", role: "user", department_id: null });
  }
  return (
    <section className="rounded border bg-white p-4">
      <h2 className="mb-2 font-semibold">用户</h2>
      <ul className="mb-3 list-disc pl-5 text-sm text-slate-700">
        {users.map((u) => <li key={u.id}>{u.display_name}（{u.email}，{u.role}）</li>)}
      </ul>
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input className="rounded border px-2 py-1" value={f.email}
          onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="邮箱" />
        <input className="rounded border px-2 py-1" type="password" value={f.password}
          onChange={(e) => setF({ ...f, password: e.target.value })} placeholder="密码" />
        <input className="rounded border px-2 py-1" value={f.display_name}
          onChange={(e) => setF({ ...f, display_name: e.target.value })} placeholder="姓名" />
        <select className="rounded border px-2 py-1" value={f.role}
          onChange={(e) => setF({ ...f, role: e.target.value })}>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <select className="rounded border px-2 py-1" value={f.department_id ?? ""}
          onChange={(e) => setF({ ...f, department_id: e.target.value || null })}>
          <option value="">（无部门）</option>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <button className="rounded bg-slate-800 px-3 text-white">新建用户</button>
      </form>
    </section>
  );
}
```

- [ ] **Step 3：`Layout.tsx` 加 admin 入口**（在 问答 链接后）

```tsx
{user?.role === "admin" && (
  <Link to="/admin" className="text-slate-600 hover:text-slate-900">管理</Link>
)}
```

- [ ] **Step 4：`App.tsx` 加路由**（受保护布局内）：`import AdminPage from "./pages/AdminPage";` 与 `<Route path="/admin" element={<AdminPage />} />`。

- [ ] **Step 5：`pnpm build` + `pnpm test` 通过；提交**

```bash
git add web/src/pages/AdminPage.tsx web/src/api/types.ts web/src/components/Layout.tsx web/src/App.tsx
git commit -m "feat(web): admin 组织管理界面（部门/团队/用户 CRUD，仅 admin 可见）"
```

---

## Self-Review
- **Spec 覆盖**：补齐 spec §2.1 第 2 项（部门多级树/团队跨部门成员/用户归属）的管理 UI；端点 §10（GET/POST departments/teams、teams/{id}/members、users）。✓
- **权限**：org 路由整体 `require_admin`，新 GET 同样仅 admin（测试含非 admin 403）；前端入口按 role 隐藏（纵深防御，真正拦截在后端）。✓
- **一致性**：复用 apiFetch/postJson、既有页面/表单模式；类型新增 Department/Team。✓
- **未含**：编辑/删除（MVP 只做新建+列表）；部门树可视化（用简单列表 + 子部门标记）。

## 执行交接
按 executing-plans 逐 Task 实现，后端 TDD、前端 build/test 通过即提交。

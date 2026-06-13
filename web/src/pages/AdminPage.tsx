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

      <DeptSection
        depts={depts}
        onCreate={(name, parentId) =>
          run(() => postJson("/departments", { name, parent_id: parentId }), "部门已创建")
        }
      />

      <TeamSection
        teams={teams}
        users={users}
        onCreate={(name) => run(() => postJson("/teams", { name }), "团队已创建")}
        onAddMember={(teamId, userId) =>
          run(() => postJson(`/teams/${teamId}/members`, { user_id: userId }), "成员已加入")
        }
      />

      <UserSection
        users={users}
        depts={depts}
        onCreate={(body) => run(() => postJson("/users", body), "用户已创建")}
      />
    </div>
  );
}

function DeptSection({
  depts,
  onCreate,
}: {
  depts: Department[];
  onCreate: (name: string, parentId: string | null) => void;
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
          <li key={d.id}>
            {d.name}
            {d.parent_id ? "（子部门）" : ""}
          </li>
        ))}
      </ul>
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input className="rounded border px-2 py-1" value={name}
          onChange={(e) => setName(e.target.value)} placeholder="部门名" />
        <select className="rounded border px-2 py-1" value={parent}
          onChange={(e) => setParent(e.target.value)}>
          <option value="">（顶级部门）</option>
          {depts.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <button className="rounded bg-slate-800 px-3 text-white">新建部门</button>
      </form>
    </section>
  );
}

function TeamSection({
  teams,
  users,
  onCreate,
  onAddMember,
}: {
  teams: Team[];
  users: UserOut[];
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
        {teams.map((t) => (
          <li key={t.id}>{t.name}</li>
        ))}
      </ul>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name) {
            onCreate(name);
            setName("");
          }
        }}
        className="mb-2 flex gap-2"
      >
        <input className="rounded border px-2 py-1" value={name}
          onChange={(e) => setName(e.target.value)} placeholder="团队名" />
        <button className="rounded bg-slate-800 px-3 text-white">新建团队</button>
      </form>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (teamId && userId) onAddMember(teamId, userId);
        }}
        className="flex flex-wrap gap-2"
      >
        <select className="rounded border px-2 py-1" value={teamId}
          onChange={(e) => setTeamId(e.target.value)}>
          <option value="">选团队</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <select className="rounded border px-2 py-1" value={userId}
          onChange={(e) => setUserId(e.target.value)}>
          <option value="">选用户</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.display_name}</option>
          ))}
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

function UserSection({
  users,
  depts,
  onCreate,
}: {
  users: UserOut[];
  depts: Department[];
  onCreate: (body: NewUser) => void;
}) {
  const [f, setF] = useState<NewUser>({
    email: "",
    password: "",
    display_name: "",
    role: "user",
    department_id: null,
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
        {users.map((u) => (
          <li key={u.id}>
            {u.display_name}（{u.email}，{u.role}）
          </li>
        ))}
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
          {depts.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <button className="rounded bg-slate-800 px-3 text-white">新建用户</button>
      </form>
    </section>
  );
}

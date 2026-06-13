import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Building2, UserPlus, Users } from "lucide-react";

import { apiFetch, postJson } from "../api/client";
import type { Department, Team, UserOut } from "../api/types";
import { Badge, PageHeader } from "../components/ui";

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="card p-6">
      <h2 className="mb-4 flex items-center gap-2.5 font-display text-lg font-semibold tracking-tight">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent-soft text-accent-dark">
          {icon}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

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
    <div>
      <PageHeader title="组织管理" subtitle="部门、团队与用户" />
      {msg && <p className="mb-4 text-sm text-accent-dark">{msg}</p>}
      <div className="space-y-5">
        <Section icon={<Building2 className="h-[18px] w-[18px]" />} title="部门">
          <DeptList depts={depts} />
          <DeptForm
            depts={depts}
            onCreate={(name, parentId) =>
              run(() => postJson("/departments", { name, parent_id: parentId }), "部门已创建")
            }
          />
        </Section>

        <Section icon={<Users className="h-[18px] w-[18px]" />} title="团队">
          <div className="mb-4 flex flex-wrap gap-2">
            {teams.length === 0 && <span className="text-sm text-ink-faint">暂无团队</span>}
            {teams.map((t) => (
              <Badge key={t.id} tone="team">
                {t.name}
              </Badge>
            ))}
          </div>
          <TeamForms
            teams={teams}
            users={users}
            onCreate={(name) => run(() => postJson("/teams", { name }), "团队已创建")}
            onAddMember={(teamId, userId) =>
              run(() => postJson(`/teams/${teamId}/members`, { user_id: userId }), "成员已加入")
            }
          />
        </Section>

        <Section icon={<UserPlus className="h-[18px] w-[18px]" />} title="用户">
          <ul className="mb-4 divide-y divide-line rounded-xl border border-line">
            {users.map((u) => (
              <li key={u.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-accent-soft font-display text-xs font-semibold text-accent-dark">
                  {u.display_name[0]}
                </span>
                <span className="font-medium text-ink">{u.display_name}</span>
                <span className="text-ink-faint">{u.email}</span>
                <span className="ml-auto">
                  <Badge tone={u.role === "admin" ? "company" : "personal"}>{u.role}</Badge>
                </span>
              </li>
            ))}
          </ul>
          <UserForm
            depts={depts}
            onCreate={(body) => run(() => postJson("/users", body), "用户已创建")}
          />
        </Section>
      </div>
    </div>
  );
}

function DeptList({ depts }: { depts: Department[] }) {
  if (depts.length === 0) return <p className="mb-4 text-sm text-ink-faint">暂无部门</p>;
  return (
    <ul className="mb-4 flex flex-wrap gap-2">
      {depts.map((d) => (
        <Badge key={d.id} tone="department">
          {d.name}
          {d.parent_id ? " · 子部门" : ""}
        </Badge>
      ))}
    </ul>
  );
}

function DeptForm({
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
    <form onSubmit={submit} className="flex flex-wrap gap-2">
      <input
        className="field max-w-[12rem]"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="部门名"
      />
      <select className="field max-w-[12rem]" value={parent} onChange={(e) => setParent(e.target.value)}>
        <option value="">（顶级部门）</option>
        {depts.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      <button className="btn-primary">新建部门</button>
    </form>
  );
}

function TeamForms({
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
    <div className="space-y-2">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name) {
            onCreate(name);
            setName("");
          }
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          className="field max-w-[12rem]"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="团队名"
        />
        <button className="btn-primary">新建团队</button>
      </form>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (teamId && userId) onAddMember(teamId, userId);
        }}
        className="flex flex-wrap gap-2"
      >
        <select className="field max-w-[10rem]" value={teamId} onChange={(e) => setTeamId(e.target.value)}>
          <option value="">选团队</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <select className="field max-w-[10rem]" value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="">选用户</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name}
            </option>
          ))}
        </select>
        <button className="btn-ghost">加入成员</button>
      </form>
    </div>
  );
}

interface NewUser {
  email: string;
  password: string;
  display_name: string;
  role: string;
  department_id: string | null;
}

function UserForm({
  depts,
  onCreate,
}: {
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
    <form onSubmit={submit} className="flex flex-wrap gap-2">
      <input
        className="field max-w-[12rem]"
        value={f.email}
        onChange={(e) => setF({ ...f, email: e.target.value })}
        placeholder="邮箱"
      />
      <input
        className="field max-w-[10rem]"
        type="password"
        value={f.password}
        onChange={(e) => setF({ ...f, password: e.target.value })}
        placeholder="密码"
      />
      <input
        className="field max-w-[8rem]"
        value={f.display_name}
        onChange={(e) => setF({ ...f, display_name: e.target.value })}
        placeholder="姓名"
      />
      <select
        className="field max-w-[7rem]"
        value={f.role}
        onChange={(e) => setF({ ...f, role: e.target.value })}
      >
        <option value="user">user</option>
        <option value="admin">admin</option>
      </select>
      <select
        className="field max-w-[9rem]"
        value={f.department_id ?? ""}
        onChange={(e) => setF({ ...f, department_id: e.target.value || null })}
      >
        <option value="">（无部门）</option>
        {depts.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      <button className="btn-primary">新建用户</button>
    </form>
  );
}

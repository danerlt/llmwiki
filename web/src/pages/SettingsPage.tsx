import { useEffect, useState, type FormEvent } from "react";
import { Download, KeyRound, Plug, Trash2 } from "lucide-react";

import { apiFetch, del, getToken, postJson, setToken } from "../api/client";
import type { ApiKey } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PageHeader } from "../components/ui";

function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    apiFetch<ApiKey[]>("/api-keys").then(setKeys).catch(() => {});
  }
  useEffect(load, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const r = await postJson<ApiKey & { key: string }>("/api-keys", { name });
      setCreated(r.key);
      setName("");
      load();
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    try {
      await del(`/api-keys/${id}`);
      load();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="card max-w-2xl p-6">
      <h2 className="mb-1 flex items-center gap-1.5 font-display text-lg font-semibold">
        <Plug className="h-4 w-4" /> API Key（服务账号）
      </h2>
      <p className="mb-4 text-xs text-ink-faint">
        以你的身份编程访问 API：请求头带 <code className="font-mono">X-API-Key: &lt;key&gt;</code>。密钥仅创建时显示一次。
      </p>
      {created && (
        <div className="mb-4 rounded-xl border border-accent/40 bg-accent-soft p-3 text-sm">
          <div className="mb-1 font-medium text-accent-dark">新密钥（请立即复制，仅显示一次）</div>
          <code className="block break-all font-mono text-xs text-ink">{created}</code>
        </div>
      )}
      <form onSubmit={create} className="mb-4 flex flex-wrap gap-2">
        <input
          className="field max-w-[16rem]"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="密钥名称（如 ci-bot）"
        />
        <button className="btn-primary" disabled={busy || !name.trim()}>
          生成密钥
        </button>
      </form>
      {keys.length > 0 && (
        <ul className="divide-y divide-line rounded-xl border border-line">
          {keys.map((k) => (
            <li key={k.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className={`font-medium ${k.revoked ? "text-ink-faint line-through" : "text-ink"}`}>
                {k.name}
              </span>
              <span className="font-mono text-xs text-ink-faint">lk_{k.prefix}_…</span>
              {k.revoked && <span className="text-xs text-red-500">已吊销</span>}
              {!k.revoked && (
                <button
                  onClick={() => revoke(k.id)}
                  className="ml-auto text-ink-faint transition hover:text-red-600"
                  title="吊销"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  async function exportData() {
    const res = await fetch("/api/me/export", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) return;
    const blob = new Blob([JSON.stringify(await res.json(), null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "my_data.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    setErr("");
    if (newPw.length < 8) {
      setErr("新密码至少 8 位");
      return;
    }
    if (newPw !== confirm) {
      setErr("两次输入的新密码不一致");
      return;
    }
    setSaving(true);
    try {
      const r = await postJson<{ access_token: string }>("/auth/change-password", {
        old_password: oldPw,
        new_password: newPw,
      });
      setToken(r.access_token); // 保持当前会话（其它会话已失效）
      setOldPw("");
      setNewPw("");
      setConfirm("");
      setMsg("密码已更新，其它设备的登录已失效。");
    } catch (e) {
      setErr(e instanceof Error && e.message ? e.message : "修改失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="账号设置" subtitle={user?.email} />
      <div className="card max-w-md p-6">
        <h2 className="mb-4 flex items-center gap-1.5 font-display text-lg font-semibold">
          <KeyRound className="h-4 w-4" /> 修改密码
        </h2>
        <form onSubmit={submit} className="space-y-3">
          <input
            type="password"
            className="field"
            value={oldPw}
            onChange={(e) => setOldPw(e.target.value)}
            placeholder="当前密码"
            autoComplete="current-password"
          />
          <input
            type="password"
            className="field"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            placeholder="新密码（至少 8 位）"
            autoComplete="new-password"
          />
          <input
            type="password"
            className="field"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="确认新密码"
            autoComplete="new-password"
          />
          {err && <p className="text-sm text-red-600">{err}</p>}
          {msg && <p className="text-sm text-accent-dark">{msg}</p>}
          <button className="btn-primary" disabled={saving || !oldPw || !newPw}>
            {saving ? "保存中…" : "更新密码"}
          </button>
        </form>
      </div>
      <ApiKeys />
      <div className="card max-w-md p-6">
        <h2 className="mb-1 flex items-center gap-1.5 font-display text-lg font-semibold">
          <Download className="h-4 w-4" /> 数据与隐私
        </h2>
        <p className="mb-4 text-xs text-ink-faint">导出你的个人数据（资料、评论、收藏、API Key 元数据）。</p>
        <button onClick={exportData} className="btn-ghost">
          <Download className="h-4 w-4" /> 导出我的数据 (JSON)
        </button>
      </div>
    </div>
  );
}

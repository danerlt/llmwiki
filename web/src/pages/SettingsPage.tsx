import { useState, type FormEvent } from "react";
import { KeyRound } from "lucide-react";

import { postJson, setToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PageHeader } from "../components/ui";

export default function SettingsPage() {
  const { user } = useAuth();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

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
    <div>
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
    </div>
  );
}

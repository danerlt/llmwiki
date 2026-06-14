import { useState, type FormEvent } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { postJson, setRefreshToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@llmwiki.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const r = await postJson<{ access_token: string; refresh_token?: string }>("/auth/login", {
        email,
        password,
      });
      if (r.refresh_token) setRefreshToken(r.refresh_token);
      await login(r.access_token);
      navigate("/");
    } catch {
      setErr("邮箱或密码错误，请重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm animate-rise">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-accent text-white shadow-lift">
            <Sparkles className="h-7 w-7" />
          </span>
          <h1 className="font-display text-4xl font-semibold tracking-tight">Lumen</h1>
          <p className="mt-1.5 text-sm text-ink-muted">把企业知识编译成会自我维护的 wiki</p>
        </div>
        <form onSubmit={onSubmit} className="card space-y-4 p-6">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-muted">邮箱</label>
            <input
              className="field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-muted">密码</label>
            <input
              className="field"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {err && <p className="text-sm text-red-600">{err}</p>}
          <button className="btn-primary w-full" disabled={loading}>
            {loading ? (
              "登录中…"
            ) : (
              <>
                登录 <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-faint">
          默认管理员 admin@llmwiki.com / admin12345
        </p>
      </div>
    </div>
  );
}

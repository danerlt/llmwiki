import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { postJson } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@llmwiki.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await postJson<{ access_token: string }>("/auth/login", { email, password });
      await login(r.access_token);
      navigate("/");
    } catch {
      setErr("登录失败：邮箱或密码错误");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="w-80 space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">企业 LLM-Wiki 登录</h1>
        <input
          className="w-full rounded border px-3 py-2"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="邮箱"
        />
        <input
          className="w-full rounded border px-3 py-2"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
        />
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="w-full rounded bg-slate-800 py-2 text-white hover:bg-slate-700">
          登录
        </button>
      </form>
    </div>
  );
}

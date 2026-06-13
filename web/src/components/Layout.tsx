import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <Link to="/" className="font-semibold">
          LLM-Wiki
        </Link>
        <Link to="/search" className="text-slate-600 hover:text-slate-900">
          搜索
        </Link>
        <Link to="/query" className="text-slate-600 hover:text-slate-900">
          问答
        </Link>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-slate-500">
            {user?.display_name}（{user?.role}）
          </span>
          <button onClick={logout} className="rounded border px-2 py-1 hover:bg-slate-100">
            退出
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-4xl p-6">
        <Outlet />
      </main>
    </div>
  );
}

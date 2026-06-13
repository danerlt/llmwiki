import type { ReactNode } from "react";

import {
  Inbox,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Search,
  Sparkles,
  Users,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

function NavItem({ to, icon, label }: { to: string; icon: ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
          isActive
            ? "bg-accent-soft font-medium text-accent-dark"
            : "text-ink-muted hover:bg-paper hover:text-ink"
        }`
      }
    >
      <span className="grid h-[18px] w-[18px] place-items-center">{icon}</span>
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-line bg-card/70 px-4 py-5 backdrop-blur-sm">
        <button
          onClick={() => navigate("/")}
          className="mb-8 flex items-center gap-2.5 px-2 text-left"
        >
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-soft">
            <Sparkles className="h-5 w-5" />
          </span>
          <span>
            <span className="block font-display text-xl font-semibold leading-none tracking-tight">
              Lumen
            </span>
            <span className="text-xs text-ink-faint">企业知识库</span>
          </span>
        </button>

        <nav className="flex flex-1 flex-col gap-1">
          <NavItem to="/" icon={<LayoutDashboard className="h-[18px] w-[18px]" />} label="概览" />
          <NavItem to="/search" icon={<Search className="h-[18px] w-[18px]" />} label="搜索" />
          <NavItem to="/query" icon={<Sparkles className="h-[18px] w-[18px]" />} label="智能问答" />
          <NavItem to="/reviews" icon={<Inbox className="h-[18px] w-[18px]" />} label="审核队列" />
          {isAdmin && (
            <>
              <div className="mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                管理
              </div>
              <NavItem to="/admin" icon={<Users className="h-[18px] w-[18px]" />} label="组织管理" />
              <NavItem to="/audit" icon={<ScrollText className="h-[18px] w-[18px]" />} label="审计日志" />
            </>
          )}
        </nav>

        <div className="mt-4 flex items-center gap-3 rounded-xl border border-line bg-paper px-3 py-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-soft font-display text-sm font-semibold text-accent-dark">
            {user?.display_name?.[0] ?? "?"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-ink">{user?.display_name}</div>
            <div className="text-xs text-ink-faint">{isAdmin ? "管理员" : "成员"}</div>
          </div>
          <button
            onClick={logout}
            title="退出登录"
            className="text-ink-faint transition hover:text-ink"
          >
            <LogOut className="h-[18px] w-[18px]" />
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl animate-rise px-8 py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

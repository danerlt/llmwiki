import { useEffect, useState, type ReactNode } from "react";
import { ChevronRight, FileText, Inbox, Layers, Library, Search, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { KB, PageOut, Stats } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Badge, EmptyState, Spinner } from "../components/ui";

const SCOPE: Record<string, string> = {
  company: "公司",
  department: "部门",
  team: "团队",
  personal: "个人",
};

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-dark">
        {icon}
      </span>
      <div>
        <div className="font-display text-2xl font-semibold leading-none">{value}</div>
        <div className="mt-1 text-xs text-ink-muted">{label}</div>
      </div>
    </div>
  );
}

export default function KbListPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<PageOut[]>([]);
  const [kbs, setKbs] = useState<KB[] | null>(null);

  useEffect(() => {
    apiFetch<Stats>("/stats").then(setStats).catch(() => {});
    apiFetch<PageOut[]>("/recent-pages").then(setRecent).catch(() => {});
    apiFetch<KB[]>("/kbs").then(setKbs).catch(() => {});
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          你好，{user?.display_name}
        </h1>
        <p className="mt-1.5 text-sm text-ink-muted">这是你的知识库概览</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={<Library className="h-5 w-5" />} label="可见知识库" value={stats?.kb_count ?? 0} />
        <Stat icon={<FileText className="h-5 w-5" />} label="wiki 页面" value={stats?.page_count ?? 0} />
        <Stat icon={<Layers className="h-5 w-5" />} label="源文件" value={stats?.source_count ?? 0} />
        <Stat icon={<Inbox className="h-5 w-5" />} label="待我审核" value={stats?.pending_reviews ?? 0} />
      </div>

      <div className="flex flex-wrap gap-3">
        <Link to="/query" className="btn-primary">
          <Sparkles className="h-4 w-4" /> 智能问答
        </Link>
        <Link to="/search" className="btn-ghost">
          <Search className="h-4 w-4" /> 搜索知识
        </Link>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <section>
          <h2 className="mb-3 font-display text-lg font-semibold tracking-tight">知识库</h2>
          {!kbs ? (
            <Spinner />
          ) : kbs.length === 0 ? (
            <EmptyState icon={<Library className="h-8 w-8" />} title="暂无可见知识库" />
          ) : (
            <div className="space-y-2.5">
              {kbs.map((kb) => (
                <Link
                  key={kb.id}
                  to={`/kbs/${kb.id}/pages`}
                  className="card group flex items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:shadow-lift"
                >
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-dark">
                    <Library className="h-[18px] w-[18px]" />
                  </span>
                  <span className="min-w-0 flex-1 truncate font-medium text-ink">{kb.name}</span>
                  <Badge tone={kb.scope_type}>{SCOPE[kb.scope_type] ?? kb.scope_type}</Badge>
                  <span className="text-xs text-ink-faint">{kb.page_count ?? 0} 页</span>
                  <ChevronRight className="h-4 w-4 text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-accent" />
                </Link>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="mb-3 font-display text-lg font-semibold tracking-tight">最近更新</h2>
          {recent.length === 0 ? (
            <p className="text-sm text-ink-faint">还没有页面</p>
          ) : (
            <ul className="card divide-y divide-line overflow-hidden">
              {recent.map((p) => (
                <li key={p.id}>
                  <Link
                    to={`/pages/${p.id}`}
                    className="flex items-center gap-2.5 px-4 py-3 text-sm transition hover:bg-paper"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
                    <span className="flex-1 truncate text-ink">{p.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

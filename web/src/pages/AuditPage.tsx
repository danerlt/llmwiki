import { useCallback, useEffect, useState } from "react";
import { ScrollText } from "lucide-react";

import { apiFetch } from "../api/client";
import type { AuditEventOut, Paginated } from "../api/types";
import { EmptyState, PageHeader, Spinner } from "../components/ui";

const PAGE = 50;

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEventOut[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async (offset: number) => {
    const r = await apiFetch<Paginated<AuditEventOut>>(`/audit?limit=${PAGE}&offset=${offset}`);
    setTotal(r.total);
    setEvents((prev) => (offset === 0 ? r.items : [...(prev ?? []), ...r.items]));
  }, []);

  useEffect(() => {
    load(0).catch(() => setErr("加载审计日志失败（需要 admin 权限）"));
  }, [load]);

  async function more() {
    setLoadingMore(true);
    try {
      await load(events?.length ?? 0);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="审计日志"
        subtitle="关键动作的不可变留痕（谁 · 何时 · 做了什么）"
        action={total > 0 ? <span className="text-sm text-ink-muted">共 {total} 条</span> : undefined}
      />
      {err && <p className="text-red-600">{err}</p>}
      {!events && !err ? (
        <Spinner />
      ) : events && events.length === 0 ? (
        <EmptyState icon={<ScrollText className="h-8 w-8" />} title="暂无审计事件" />
      ) : (
        events && (
          <>
            <div className="card overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line bg-paper text-xs uppercase tracking-wider text-ink-faint">
                    <th className="px-5 py-3 font-medium">时间</th>
                    <th className="px-5 py-3 font-medium">操作者</th>
                    <th className="px-5 py-3 font-medium">动作</th>
                    <th className="px-5 py-3 font-medium">对象</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {events.map((e) => (
                    <tr key={e.id} className="align-top transition hover:bg-paper/60">
                      <td className="whitespace-nowrap px-5 py-3 text-ink-muted">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3">{e.actor_email}</td>
                      <td className="px-5 py-3">
                        <span className="rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent-dark">
                          {e.action}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-ink-faint">
                        {e.target_type ?? "—"}
                        {e.detail && (
                          <span className="ml-2 font-mono text-xs">{JSON.stringify(e.detail)}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {events.length < total && (
              <div className="mt-4 flex justify-center">
                <button onClick={more} disabled={loadingMore} className="btn-ghost">
                  {loadingMore ? "加载中…" : `加载更多（剩 ${total - events.length} 条）`}
                </button>
              </div>
            )}
          </>
        )
      )}
    </div>
  );
}

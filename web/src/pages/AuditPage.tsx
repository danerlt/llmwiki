import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";

import { apiFetch } from "../api/client";
import type { AuditEventOut } from "../api/types";
import { EmptyState, PageHeader, Spinner } from "../components/ui";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEventOut[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<AuditEventOut[]>("/audit")
      .then(setEvents)
      .catch(() => setErr("加载审计日志失败（需要 admin 权限）"));
  }, []);

  return (
    <div>
      <PageHeader title="审计日志" subtitle="关键动作的不可变留痕（谁 · 何时 · 做了什么）" />
      {err && <p className="text-red-600">{err}</p>}
      {!events && !err ? (
        <Spinner />
      ) : events && events.length === 0 ? (
        <EmptyState icon={<ScrollText className="h-8 w-8" />} title="暂无审计事件" />
      ) : (
        events && (
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
        )
      )}
    </div>
  );
}

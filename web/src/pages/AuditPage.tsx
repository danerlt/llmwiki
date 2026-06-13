import { useEffect, useState } from "react";

import { apiFetch } from "../api/client";
import type { AuditEventOut } from "../api/types";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEventOut[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<AuditEventOut[]>("/audit")
      .then(setEvents)
      .catch(() => setErr("加载审计日志失败（需要 admin 权限）"));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">审计日志</h1>
      {err && <p className="text-red-600">{err}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-slate-500">
            <th className="py-2">时间</th>
            <th>操作者</th>
            <th>动作</th>
            <th>对象</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id} className="border-b align-top">
              <td className="py-1.5 text-slate-500">{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.actor_email}</td>
              <td>
                <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs">
                  {e.action}
                </span>
              </td>
              <td className="text-slate-500">{e.target_type ?? "-"}</td>
              <td className="text-slate-400">{e.detail ? JSON.stringify(e.detail) : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {events.length === 0 && !err && <p className="mt-3 text-slate-500">暂无审计事件</p>}
    </div>
  );
}

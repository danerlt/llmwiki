import { useEffect, useState } from "react";
import { Check, Inbox, X } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch, postJson } from "../api/client";
import type { PromotionOut } from "../api/types";
import { EmptyState, PageHeader } from "../components/ui";

export default function ReviewsPage() {
  const [items, setItems] = useState<PromotionOut[] | null>(null);
  const [msg, setMsg] = useState("");

  function reload() {
    apiFetch<PromotionOut[]>("/reviews").then(setItems).catch(() => setMsg("加载审核队列失败"));
  }
  useEffect(reload, []);

  async function decide(id: string, action: "approve" | "reject") {
    setMsg("");
    try {
      await postJson(`/reviews/${id}/${action}`, {});
      setMsg(action === "approve" ? "已批准并晋升" : "已拒绝");
      reload();
    } catch {
      setMsg("操作失败（无目标知识库写权限或已处理）");
    }
  }

  return (
    <div>
      <PageHeader title="审核队列" subtitle="审批「把知识晋升到你有写权限的知识库」的申请" />
      {msg && <p className="mb-3 text-sm text-accent-dark">{msg}</p>}
      {items === null ? null : items.length === 0 ? (
        <EmptyState
          icon={<Inbox className="h-8 w-8" />}
          title="没有待你审核的申请"
          hint="当有人申请把知识晋升到你管理的知识库时，会出现在这里。"
        />
      ) : (
        <ul className="space-y-3">
          {items.map((it) => (
            <li key={it.id} className="card flex items-center justify-between gap-4 p-4">
              <div className="min-w-0 text-sm">
                <Link
                  to={`/pages/${it.page_id}`}
                  className="font-medium text-ink hover:text-accent-dark"
                >
                  {it.page_title}
                </Link>
                <span className="mx-2 text-ink-faint">→</span>
                <span className="font-medium text-accent-dark">{it.to_kb_name}</span>
                {it.note && <p className="mt-1 text-ink-muted">{it.note}</p>}
              </div>
              <div className="flex shrink-0 gap-2">
                <button onClick={() => decide(it.id, "approve")} className="btn-primary">
                  <Check className="h-4 w-4" /> 批准
                </button>
                <button onClick={() => decide(it.id, "reject")} className="btn-ghost">
                  <X className="h-4 w-4" /> 拒绝
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch, postJson } from "../api/client";
import type { PromotionOut } from "../api/types";

export default function ReviewsPage() {
  const [items, setItems] = useState<PromotionOut[]>([]);
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
      setMsg("操作失败（无目标 KB 写权限或已处理）");
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">审核队列</h1>
      {msg && <p className="mb-2 text-sm text-slate-600">{msg}</p>}
      {items.length === 0 && <p className="text-slate-500">没有待你审核的晋升申请</p>}
      <ul className="space-y-2">
        {items.map((it) => (
          <li
            key={it.id}
            className="flex items-center justify-between rounded border bg-white px-4 py-3"
          >
            <span className="text-sm">
              <Link to={`/pages/${it.page_id}`} className="text-blue-600 hover:underline">
                {it.page_title}
              </Link>
              {" → "}
              <span className="font-medium">{it.to_kb_name}</span>
              {it.note ? <span className="text-slate-400">（{it.note}）</span> : null}
            </span>
            <span className="flex gap-2">
              <button
                onClick={() => decide(it.id, "approve")}
                className="rounded bg-slate-800 px-3 py-1 text-sm text-white hover:bg-slate-700"
              >
                批准
              </button>
              <button
                onClick={() => decide(it.id, "reject")}
                className="rounded border px-3 py-1 text-sm hover:bg-slate-100"
              >
                拒绝
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

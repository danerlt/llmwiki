import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken, setToken } from "../api/client";
import type { PageOut, SourceOut } from "../api/types";

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
  const [pages, setPages] = useState<PageOut[]>([]);
  const [source, setSource] = useState<SourceOut | null>(null);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);

  function loadPages() {
    apiFetch<PageOut[]>(`/kbs/${kbId}/pages`)
      .then(setPages)
      .catch(() => setErr("加载页面失败"));
  }

  useEffect(() => {
    cancelledRef.current = false;
    loadPages();
    return () => {
      cancelledRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbId]);

  function pollStatus(sourceId: string) {
    if (timerRef.current) clearTimeout(timerRef.current); // 取消上一轮，避免多次上传产生并发轮询
    const tick = async () => {
      try {
        const s = await apiFetch<SourceOut>(`/sources/${sourceId}`);
        if (cancelledRef.current) return; // 卸载后不再 setState
        setSource(s);
        if (s.status === "pending" || s.status === "processing") {
          timerRef.current = window.setTimeout(tick, 1500);
        } else {
          loadPages();
        }
      } catch {
        /* 轮询出错（含 401 已由 apiFetch 跳转登录）则停止 */
      }
    };
    void tick();
  }

  async function upload(e: FormEvent) {
    e.preventDefault();
    setErr("");
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`/api/kbs/${kbId}/sources`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form,
      });
      if (res.status === 401) {
        setToken(null);
        location.assign("/login");
        return;
      }
      if (!res.ok) {
        setErr(`上传失败：${await res.text()}`);
        return;
      }
      const created = (await res.json()) as { source_id: string };
      pollStatus(created.source_id);
    } catch {
      setErr("网络异常，请重试");
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">知识库页面</h1>
      <form onSubmit={upload} className="mb-6 flex items-center gap-3 rounded border bg-white p-4">
        <input ref={fileRef} type="file" accept=".md,.txt,.pdf" className="text-sm" />
        <button className="rounded bg-slate-800 px-3 py-1 text-white hover:bg-slate-700">
          上传并摄入
        </button>
        {source && (
          <span className="text-sm text-slate-600">
            {source.filename}：{source.status}
            {source.error ? `（${source.error}）` : ""}
          </span>
        )}
      </form>
      {err && <p className="text-red-600">{err}</p>}
      <ul className="space-y-1">
        {pages.map((p) => (
          <li key={p.id}>
            <Link to={`/pages/${p.id}`} className="text-blue-600 hover:underline">
              {p.title} <span className="text-xs text-slate-400">[{p.page_type}]</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

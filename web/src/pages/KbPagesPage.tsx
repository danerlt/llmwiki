import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken } from "../api/client";
import type { PageOut, SourceOut } from "../api/types";

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
  const [pages, setPages] = useState<PageOut[]>([]);
  const [source, setSource] = useState<SourceOut | null>(null);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  function loadPages() {
    apiFetch<PageOut[]>(`/kbs/${kbId}/pages`)
      .then(setPages)
      .catch(() => setErr("加载页面失败"));
  }
  useEffect(loadPages, [kbId]);

  function pollStatus(sourceId: string) {
    const tick = async () => {
      const s = await apiFetch<SourceOut>(`/sources/${sourceId}`);
      setSource(s);
      if (s.status === "pending" || s.status === "processing") {
        setTimeout(tick, 1500);
      } else {
        loadPages(); // done/failed 后刷新页列表
      }
    };
    void tick();
  }

  async function upload(e: FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/kbs/${kbId}/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    });
    if (!res.ok) {
      setErr("上传失败（可能无写权限）");
      return;
    }
    const created = (await res.json()) as { source_id: string };
    pollStatus(created.source_id);
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

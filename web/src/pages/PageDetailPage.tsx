import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiFetch, postJson } from "../api/client";
import type { KB, PageDetail, PageOut } from "../api/types";
import Markdown from "../components/Markdown";
import { resolveWikilinks } from "../lib/wikilink";

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [slugMap, setSlugMap] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const [kbs, setKbs] = useState<KB[]>([]);
  const [target, setTarget] = useState("");
  const [promoteMsg, setPromoteMsg] = useState("");

  useEffect(() => {
    let cancelled = false;
    setPage(null);
    setErr("");
    apiFetch<PageDetail>(`/pages/${pageId}`)
      .then(async (p) => {
        if (cancelled) return;
        setPage(p);
        const siblings = await apiFetch<PageOut[]>(`/kbs/${p.kb_id}/pages`);
        if (!cancelled) setSlugMap(Object.fromEntries(siblings.map((s) => [s.slug, s.id])));
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setErr("页面不存在");
        else if (e instanceof ApiError && e.status === 403) setErr("无权访问该页面");
        else setErr("加载失败，请稍后重试");
      });
    apiFetch<KB[]>("/kbs")
      .then((ks) => {
        if (!cancelled) setKbs(ks);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pageId]);

  async function promote() {
    if (!target) return;
    setPromoteMsg("");
    try {
      await postJson(`/pages/${pageId}/promote`, { to_kb_id: target });
      setPromoteMsg("已提交晋升申请，等待目标 KB 审核者批准");
    } catch {
      setPromoteMsg("申请失败");
    }
  }

  if (err) return <div className="text-red-600">{err}</div>;
  if (!page) return <div>加载中…</div>;
  return (
    <article>
      <h1 className="mb-1 text-2xl font-semibold">{page.title}</h1>
      <p className="mb-4 text-xs text-slate-400">
        {page.page_type} · slug: {page.slug}
      </p>
      <Markdown content={resolveWikilinks(page.content_md, slugMap)} />

      <div className="mt-8 rounded border bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-600">申请晋升到其它知识库</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded border px-2 py-1"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="">选择目标 KB</option>
            {kbs
              .filter((k) => k.id !== page.kb_id)
              .map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
          </select>
          <button
            onClick={promote}
            className="rounded bg-slate-800 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            申请晋升
          </button>
          {promoteMsg && <span className="text-sm text-slate-600">{promoteMsg}</span>}
        </div>
      </div>
    </article>
  );
}

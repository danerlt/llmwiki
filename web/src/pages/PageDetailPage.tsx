import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiFetch } from "../api/client";
import type { PageDetail, PageOut } from "../api/types";
import Markdown from "../components/Markdown";
import { resolveWikilinks } from "../lib/wikilink";

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [slugMap, setSlugMap] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");

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
    return () => {
      cancelled = true;
    };
  }, [pageId]);

  if (err) return <div className="text-red-600">{err}</div>;
  if (!page) return <div>加载中…</div>;
  return (
    <article>
      <h1 className="mb-1 text-2xl font-semibold">{page.title}</h1>
      <p className="mb-4 text-xs text-slate-400">
        {page.page_type} · slug: {page.slug}
      </p>
      <Markdown content={resolveWikilinks(page.content_md, slugMap)} />
    </article>
  );
}

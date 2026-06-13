import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { PageDetail, PageOut } from "../api/types";
import Markdown from "../components/Markdown";
import { resolveWikilinks } from "../lib/wikilink";

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [slugMap, setSlugMap] = useState<Record<string, string>>({});

  useEffect(() => {
    apiFetch<PageDetail>(`/pages/${pageId}`).then(async (p) => {
      setPage(p);
      const siblings = await apiFetch<PageOut[]>(`/kbs/${p.kb_id}/pages`);
      setSlugMap(Object.fromEntries(siblings.map((s) => [s.slug, s.id])));
    });
  }, [pageId]);

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

import { useEffect, useState } from "react";
import { ArrowLeft, ArrowUpRight, FileText, Link2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, apiFetch, postJson } from "../api/client";
import type { KB, PageDetail, PageOut } from "../api/types";
import Markdown from "../components/Markdown";
import { Badge, Spinner } from "../components/ui";
import { resolveWikilinks } from "../lib/wikilink";

const PT: Record<string, string> = {
  index: "目录",
  overview: "概览",
  entity: "实体",
  concept: "概念",
  source_summary: "源摘要",
};

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const navigate = useNavigate();
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
    setPromoteMsg("");
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
      setPromoteMsg("已提交，等待目标库审核者批准。");
    } catch {
      setPromoteMsg("申请失败");
    }
  }

  if (err) return <p className="text-red-600">{err}</p>;
  if (!page) return <Spinner />;

  return (
    <article>
      <button
        onClick={() => navigate(-1)}
        className="mb-5 inline-flex items-center gap-1.5 text-sm text-ink-muted transition hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" /> 返回
      </button>
      <div className="mb-6 flex items-center gap-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight">{page.title}</h1>
        <Badge>{PT[page.page_type] ?? page.page_type}</Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="card p-7">
          <Markdown content={resolveWikilinks(page.content_md, slugMap)} />
        </div>

        <aside className="space-y-4">
          <div className="card p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">信息</h3>
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">类型</dt>
                <dd>
                  <Badge>{PT[page.page_type] ?? page.page_type}</Badge>
                </dd>
              </div>
              {page.updated_at && (
                <div className="flex items-center justify-between">
                  <dt className="text-ink-muted">更新</dt>
                  <dd className="text-ink">{new Date(page.updated_at).toLocaleDateString()}</dd>
                </div>
              )}
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">slug</dt>
                <dd className="font-mono text-xs text-ink-faint">{page.slug}</dd>
              </div>
            </dl>
          </div>

          {page.sources && page.sources.length > 0 && (
            <div className="card p-4">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                <FileText className="h-3.5 w-3.5" /> 来源
              </h3>
              <ul className="space-y-1 text-sm text-ink">
                {page.sources.map((s) => (
                  <li key={s.id} className="truncate">
                    {s.filename}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {page.backlinks && page.backlinks.length > 0 && (
            <div className="card p-4">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                <Link2 className="h-3.5 w-3.5" /> 被引用
              </h3>
              <ul className="space-y-1.5 text-sm">
                {page.backlinks.map((b) => (
                  <li key={b.id}>
                    <Link to={`/pages/${b.id}`} className="text-accent hover:underline">
                      {b.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card p-4">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
              <ArrowUpRight className="h-3.5 w-3.5" /> 申请晋升
            </h3>
            <div className="space-y-2">
              <select
                className="field"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">选择目标知识库</option>
                {kbs
                  .filter((k) => k.id !== page.kb_id)
                  .map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.name}
                    </option>
                  ))}
              </select>
              <button onClick={promote} className="btn-ghost w-full" disabled={!target}>
                提交申请
              </button>
              {promoteMsg && <p className="text-xs text-accent-dark">{promoteMsg}</p>}
            </div>
          </div>
        </aside>
      </div>
    </article>
  );
}

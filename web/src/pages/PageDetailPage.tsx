import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bell,
  Download,
  ChevronRight,
  FileText,
  Files,
  History,
  Link2,
  Pencil,
  ShieldCheck,
  Star,
  Tag,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiFetch, del, getToken, postJson } from "../api/client";
import type { KB, PageDetail, PageOut } from "../api/types";
import Comments from "../components/Comments";
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

function AsideCard({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="card p-4">
      <h3 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [slugMap, setSlugMap] = useState<Record<string, string>>({});
  const [siblings, setSiblings] = useState<PageOut[]>([]);
  const [kbName, setKbName] = useState("");
  const [err, setErr] = useState("");
  const [kbs, setKbs] = useState<KB[]>([]);
  const [target, setTarget] = useState("");
  const [promoteMsg, setPromoteMsg] = useState("");
  const [fav, setFav] = useState(false);
  const [sub, setSub] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setPage(null);
    setErr("");
    setPromoteMsg("");
    apiFetch<PageDetail>(`/pages/${pageId}`)
      .then(async (p) => {
        if (cancelled) return;
        setPage(p);
        setFav(!!p.is_favorited);
        setSub(!!p.is_subscribed);
        const sibs = await apiFetch<PageOut[]>(`/kbs/${p.kb_id}/pages`);
        if (cancelled) return;
        setSiblings(sibs);
        setSlugMap(Object.fromEntries(sibs.map((s) => [s.slug, s.id])));
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setErr("页面不存在");
        else if (e instanceof ApiError && e.status === 403) setErr("无权访问该页面");
        else setErr("加载失败，请稍后重试");
      });
    apiFetch<KB[]>("/kbs")
      .then((ks) => {
        if (cancelled) return;
        setKbs(ks);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pageId]);

  useEffect(() => {
    if (page) setKbName(kbs.find((k) => k.id === page.kb_id)?.name ?? "知识库");
  }, [page, kbs]);

  async function toggleFav() {
    const next = !fav;
    setFav(next);
    try {
      if (next) await postJson(`/pages/${pageId}/favorite`, {});
      else await del(`/pages/${pageId}/favorite`);
    } catch {
      setFav(!next); // 失败回滚
    }
  }

  async function exportMd() {
    const res = await fetch(`/api/pages/${pageId}/markdown`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${page?.slug ?? "page"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function toggleVerify() {
    if (!page) return;
    try {
      const updated = page.verified_at
        ? await del<PageDetail>(`/pages/${pageId}/verify`)
        : await postJson<PageDetail>(`/pages/${pageId}/verify`, {});
      setPage(updated);
    } catch {
      /* ignore */
    }
  }

  async function toggleSub() {
    const next = !sub;
    setSub(next);
    try {
      if (next) await postJson(`/pages/${pageId}/subscribe`, {});
      else await del(`/pages/${pageId}/subscribe`);
    } catch {
      setSub(!next);
    }
  }

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

  const related = siblings.filter((s) => s.id !== page.id && s.page_type !== "index").slice(0, 6);

  return (
    <article>
      <nav className="mb-3 flex items-center gap-1.5 text-sm text-ink-muted">
        <Link to="/" className="hover:text-ink">
          概览
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-ink-faint" />
        <Link to={`/kbs/${page.kb_id}/pages`} className="hover:text-ink">
          {kbName}
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-ink-faint" />
        <span className="truncate text-ink">{page.title}</span>
      </nav>
      <div className="mb-6 flex items-center gap-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight">{page.title}</h1>
        <Badge>{PT[page.page_type] ?? page.page_type}</Badge>
        {page.verified_at && (
          <span
            className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600"
            title={`由 ${page.verified_by_name ?? "?"} 认证`}
          >
            <ShieldCheck className="h-4 w-4" /> 已认证
          </span>
        )}
        {page.page_type !== "index" && (
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={toggleVerify}
              className={`btn-ghost ${page.verified_at ? "text-emerald-600" : ""}`}
              title="内容认证（专家背书）"
            >
              <ShieldCheck className="h-4 w-4" /> {page.verified_at ? "取消认证" : "认证"}
            </button>
            <button
              onClick={toggleFav}
              className={`btn-ghost ${fav ? "text-amber-500" : ""}`}
              title={fav ? "取消收藏" : "收藏"}
            >
              <Star className={`h-4 w-4 ${fav ? "fill-amber-400" : ""}`} /> {fav ? "已收藏" : "收藏"}
            </button>
            <button
              onClick={toggleSub}
              className={`btn-ghost ${sub ? "text-accent-dark" : ""}`}
              title={sub ? "取消关注" : "关注此页更新"}
            >
              <Bell className={`h-4 w-4 ${sub ? "fill-accent/30" : ""}`} /> {sub ? "已关注" : "关注"}
            </button>
            <Link to={`/pages/${page.id}/edit`} className="btn-ghost">
              <Pencil className="h-4 w-4" /> 编辑
            </Link>
            <Link to={`/pages/${page.id}/history`} className="btn-ghost">
              <History className="h-4 w-4" /> 历史
            </Link>
            <button onClick={exportMd} className="btn-ghost" title="导出 Markdown">
              <Download className="h-4 w-4" /> 导出
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div>
          <div className="card p-7">
            <Markdown content={resolveWikilinks(page.content_md, slugMap)} />
          </div>
          {page.page_type !== "index" && <Comments pageId={page.id} />}
        </div>

        <aside className="space-y-4">
          <AsideCard icon={null} title="信息">
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
                <dd className="truncate font-mono text-xs text-ink-faint">{page.slug}</dd>
              </div>
            </dl>
          </AsideCard>

          {page.tags && page.tags.length > 0 && (
            <AsideCard icon={<Tag className="h-3.5 w-3.5" />} title="标签">
              <div className="flex flex-wrap gap-1.5">
                {page.tags.map((t) => (
                  <Link
                    key={t}
                    to={`/kbs/${page.kb_id}/pages?tag=${encodeURIComponent(t)}`}
                    className="chip text-xs transition hover:border-accent/40 hover:text-accent-dark"
                  >
                    {t}
                  </Link>
                ))}
              </div>
            </AsideCard>
          )}

          {page.sources && page.sources.length > 0 && (
            <AsideCard icon={<FileText className="h-3.5 w-3.5" />} title="来源">
              <ul className="space-y-1 text-sm text-ink">
                {page.sources.map((s) => (
                  <li key={s.id} className="truncate">
                    {s.filename}
                  </li>
                ))}
              </ul>
            </AsideCard>
          )}

          {page.backlinks && page.backlinks.length > 0 && (
            <AsideCard icon={<Link2 className="h-3.5 w-3.5" />} title="被引用">
              <ul className="space-y-1.5 text-sm">
                {page.backlinks.map((b) => (
                  <li key={b.id}>
                    <Link to={`/pages/${b.id}`} className="text-accent hover:underline">
                      {b.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </AsideCard>
          )}

          {page.outlinks && page.outlinks.length > 0 && (
            <AsideCard icon={<ArrowRight className="h-3.5 w-3.5" />} title="本页引用">
              <ul className="space-y-1.5 text-sm">
                {page.outlinks.map((o) => (
                  <li key={o.id}>
                    <Link to={`/pages/${o.id}`} className="text-accent hover:underline">
                      {o.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </AsideCard>
          )}

          {related.length > 0 && (
            <AsideCard icon={<Files className="h-3.5 w-3.5" />} title="相关页">
              <ul className="space-y-1.5 text-sm">
                {related.map((r) => (
                  <li key={r.id}>
                    <Link to={`/pages/${r.id}`} className="text-ink hover:text-accent-dark">
                      {r.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </AsideCard>
          )}

          <AsideCard icon={<ArrowUpRight className="h-3.5 w-3.5" />} title="申请晋升">
            <div className="space-y-2">
              <select className="field" value={target} onChange={(e) => setTarget(e.target.value)}>
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
          </AsideCard>
        </aside>
      </div>
    </article>
  );
}

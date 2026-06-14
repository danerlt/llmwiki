import { useEffect, useState } from "react";
import { GitCompare, History, RotateCcw } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiFetch, postJson } from "../api/client";
import type { PageDetail, PageVersion } from "../api/types";
import Markdown from "../components/Markdown";
import { EmptyState, PageHeader, Spinner } from "../components/ui";
import { lineDiff } from "../lib/linediff";

function unwrap(md: string): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, "$1");
}

export default function PageHistoryPage() {
  const { pageId = "" } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [versions, setVersions] = useState<PageVersion[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [reverting, setReverting] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  useEffect(() => {
    apiFetch<PageDetail>(`/pages/${pageId}`).then(setPage).catch(() => {});
    apiFetch<PageVersion[]>(`/pages/${pageId}/versions`)
      .then((v) => {
        setVersions(v);
        if (v.length) setSelected(v[0].version_no);
      })
      .catch(() => setVersions([]));
  }, [pageId]);

  async function revert(versionNo: number) {
    if (!confirm(`回滚到版本 v${versionNo}？当前内容会作为新版本保留。`)) return;
    setReverting(true);
    try {
      await postJson(`/pages/${pageId}/revert/${versionNo}`, {});
      navigate(`/pages/${pageId}`);
    } catch {
      setReverting(false);
    }
  }

  if (!versions) return <Spinner />;
  const idx = versions.findIndex((v) => v.version_no === selected);
  const current = idx >= 0 ? versions[idx] : null;
  const prev = idx >= 0 && idx + 1 < versions.length ? versions[idx + 1] : null; // 更旧的一版

  return (
    <div>
      <PageHeader
        title="历史版本"
        subtitle={page ? page.title : undefined}
        action={
          <Link to={`/pages/${pageId}`} className="btn-ghost">
            返回页面
          </Link>
        }
      />
      {versions.length === 0 ? (
        <EmptyState
          icon={<History className="h-8 w-8" />}
          title="暂无历史版本"
          hint="对该页保存编辑后，每次改动会在这里留下版本。"
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <ul className="space-y-1.5">
            {versions.map((v, i) => (
              <li key={v.version_no}>
                <button
                  onClick={() => setSelected(v.version_no)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm transition ${
                    selected === v.version_no
                      ? "border-accent/50 bg-accent-soft text-accent-dark"
                      : "border-line hover:border-accent/40"
                  }`}
                >
                  <span>
                    <span className="font-mono">v{v.version_no}</span>
                    {i === 0 && <span className="ml-2 text-xs text-ink-faint">最新</span>}
                  </span>
                  <span className="text-xs text-ink-faint">
                    {new Date(v.created_at).toLocaleString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div>
            {current && (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-display text-lg font-semibold">
                    <span className="font-mono text-accent">v{current.version_no}</span>{" "}
                    {current.title}
                  </span>
                  <div className="flex items-center gap-2">
                    {prev && (
                      <button
                        onClick={() => setShowDiff((s) => !s)}
                        className={`btn-ghost ${showDiff ? "text-accent-dark" : ""}`}
                      >
                        <GitCompare className="h-4 w-4" /> {showDiff ? "看全文" : "对比上一版"}
                      </button>
                    )}
                    <button
                      onClick={() => revert(current.version_no)}
                      disabled={reverting}
                      className="btn-ghost"
                    >
                      <RotateCcw className="h-4 w-4" /> 回滚到此版本
                    </button>
                  </div>
                </div>
                <div className="card p-7">
                  {showDiff && prev ? (
                    <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm leading-relaxed">
                      {lineDiff(prev.content_md, current.content_md).map((l, k) => (
                        <div
                          key={k}
                          className={
                            l.type === "add"
                              ? "bg-emerald-50 text-emerald-700"
                              : l.type === "del"
                                ? "bg-red-50 text-red-600 line-through"
                                : "text-ink-muted"
                          }
                        >
                          {l.type === "add" ? "+ " : l.type === "del" ? "- " : "  "}
                          {l.text || " "}
                        </div>
                      ))}
                    </pre>
                  ) : (
                    <Markdown content={unwrap(current.content_md)} />
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

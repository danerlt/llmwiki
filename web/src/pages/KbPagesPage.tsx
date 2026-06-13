import { useEffect, useRef, useState, type FormEvent } from "react";
import { ChevronRight, FileText, Upload } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken, setToken } from "../api/client";
import type { KB, PageOut, SourceOut } from "../api/types";
import { Badge, EmptyState, Spinner } from "../components/ui";

const PT_ORDER = ["overview", "entity", "concept", "source_summary", "index"];
const PT_LABEL: Record<string, string> = {
  overview: "概览",
  entity: "实体",
  concept: "概念",
  source_summary: "源摘要",
  index: "目录",
};

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
  const [kbName, setKbName] = useState("");
  const [pages, setPages] = useState<PageOut[] | null>(null);
  const [source, setSource] = useState<SourceOut | null>(null);
  const [err, setErr] = useState("");
  const [uploading, setUploading] = useState(false);
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
    apiFetch<KB[]>("/kbs")
      .then((ks) => setKbName(ks.find((k) => k.id === kbId)?.name ?? "知识库"))
      .catch(() => {});
    return () => {
      cancelledRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbId]);

  function pollStatus(sourceId: string) {
    if (timerRef.current) clearTimeout(timerRef.current);
    const tick = async () => {
      try {
        const s = await apiFetch<SourceOut>(`/sources/${sourceId}`);
        if (cancelledRef.current) return;
        setSource(s);
        if (s.status === "pending" || s.status === "processing") {
          timerRef.current = window.setTimeout(tick, 1500);
        } else {
          setUploading(false);
          loadPages();
        }
      } catch {
        setUploading(false);
      }
    };
    void tick();
  }

  async function upload(e: FormEvent) {
    e.preventDefault();
    setErr("");
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
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
        setUploading(false);
        return;
      }
      const created = (await res.json()) as { source_id: string };
      pollStatus(created.source_id);
    } catch {
      setErr("网络异常，请重试");
      setUploading(false);
    }
  }

  const groups = PT_ORDER.map((t) => ({
    t,
    items: (pages ?? []).filter((p) => p.page_type === t),
  })).filter((g) => g.items.length > 0);

  return (
    <div>
      <nav className="mb-2 flex items-center gap-1.5 text-sm text-ink-muted">
        <Link to="/" className="hover:text-ink">
          概览
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-ink-faint" />
        <span className="text-ink">{kbName}</span>
      </nav>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">{kbName || "知识库"}</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            共 {(pages ?? []).filter((p) => p.page_type !== "index").length} 个页面
          </p>
        </div>
      </div>

      <form onSubmit={upload} className="card mb-7 flex flex-wrap items-center gap-3 p-4">
        <label className="btn-ghost cursor-pointer">
          <Upload className="h-4 w-4" /> 选择文件
          <input
            ref={fileRef}
            type="file"
            accept=".md,.txt,.pdf"
            className="hidden"
            onChange={() => setSource(null)}
          />
        </label>
        <button className="btn-primary" disabled={uploading}>
          {uploading ? "摄入中…" : "上传并摄入"}
        </button>
        <span className="text-xs text-ink-faint">支持 .md / .txt / .pdf，LLM 自动编译成 wiki 页</span>
        {source && (
          <span className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-ink-muted">{source.filename}</span>
            <Badge tone={source.status}>{source.status}</Badge>
            {source.error && <span className="text-xs text-red-500">{source.error}</span>}
          </span>
        )}
      </form>
      {err && <p className="mb-3 text-red-600">{err}</p>}

      {!pages ? (
        <Spinner />
      ) : pages.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          title="还没有页面"
          hint="上传一个文档，几秒后这里会出现自动生成的 wiki 页。"
        />
      ) : (
        <div className="space-y-7">
          {groups.map((g) => (
            <section key={g.t}>
              <h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
                {PT_LABEL[g.t] ?? g.t}
                <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-normal text-ink-muted">
                  {g.items.length}
                </span>
              </h2>
              <div className="grid gap-2 sm:grid-cols-2">
                {g.items.map((p) => (
                  <Link
                    key={p.id}
                    to={`/pages/${p.id}`}
                    className="card group flex items-center gap-2.5 px-4 py-3 text-sm transition hover:-translate-y-0.5 hover:shadow-lift"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
                    <span className="flex-1 truncate text-ink">{p.title}</span>
                    <ChevronRight className="h-4 w-4 text-ink-faint transition group-hover:text-accent" />
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

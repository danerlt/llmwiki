import { useEffect, useRef, useState, type FormEvent } from "react";
import { ChevronRight, FileText, Loader2, Plus, RotateCcw, Upload } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken, postJson, setToken } from "../api/client";
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
const ST_LABEL: Record<string, string> = {
  pending: "排队中",
  processing: "摄入中",
  done: "已完成",
  failed: "失败",
};

function isBusy(s: SourceOut) {
  return s.status === "pending" || s.status === "processing";
}

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
  const [kbName, setKbName] = useState("");
  const [pages, setPages] = useState<PageOut[] | null>(null);
  const [sources, setSources] = useState<SourceOut[] | null>(null);
  const [err, setErr] = useState("");
  const [uploading, setUploading] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<number | null>(null);
  const pollingRef = useRef(false);
  // 记录当前激活的 kbId；每个请求只在自己的 kbId 仍是当前时才写状态，
  // 杜绝切换知识库时旧请求回调把 X 的数据写进正在显示 Y 的组件（跨 KB 串台）。
  const activeKbRef = useRef(kbId);

  function loadPages() {
    apiFetch<PageOut[]>(`/kbs/${kbId}/pages`)
      .then((p) => {
        if (activeKbRef.current === kbId) setPages(p);
      })
      .catch(() => setErr("加载页面失败"));
  }

  // 拉取源文件清单；若有源仍在摄入中则继续轮询，全部落定后刷新页面列表
  function loadSources() {
    apiFetch<SourceOut[]>(`/kbs/${kbId}/sources`)
      .then((list) => {
        if (activeKbRef.current !== kbId) return;
        setSources(list);
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        if (list.some(isBusy)) {
          pollingRef.current = true;
          timerRef.current = window.setTimeout(loadSources, 1800);
        } else if (pollingRef.current) {
          pollingRef.current = false;
          loadPages();
        }
      })
      .catch(() => {});
  }

  useEffect(() => {
    activeKbRef.current = kbId;
    loadPages();
    loadSources();
    apiFetch<KB[]>("/kbs")
      .then((ks) => {
        if (activeKbRef.current === kbId) setKbName(ks.find((k) => k.id === kbId)?.name ?? "知识库");
      })
      .catch(() => {});
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      pollingRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbId]);

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
        return;
      }
      if (fileRef.current) fileRef.current.value = "";
      loadSources();
    } catch {
      setErr("网络异常，请重试");
    } finally {
      setUploading(false);
    }
  }

  async function reingest(id: string) {
    setRetrying(id);
    try {
      await postJson(`/sources/${id}/reingest`, {});
      loadSources();
    } catch {
      setErr("重新摄入失败");
    } finally {
      setRetrying(null);
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
            {sources && sources.length > 0 && ` · ${sources.length} 个源文件`}
          </p>
        </div>
        <Link to={`/kbs/${kbId}/pages/new`} className="btn-primary shrink-0">
          <Plus className="h-4 w-4" /> 新建页
        </Link>
      </div>

      <form onSubmit={upload} className="card mb-5 flex flex-wrap items-center gap-3 p-4">
        <label className="btn-ghost cursor-pointer">
          <Upload className="h-4 w-4" /> 选择文件
          <input ref={fileRef} type="file" accept=".md,.txt,.pdf" className="hidden" />
        </label>
        <button className="btn-primary" disabled={uploading}>
          {uploading ? "上传中…" : "上传并摄入"}
        </button>
        <span className="text-xs text-ink-faint">支持 .md / .txt / .pdf，LLM 自动编译成 wiki 页</span>
      </form>
      {err && <p className="mb-3 text-red-600">{err}</p>}

      {sources && sources.length > 0 && (
        <section className="mb-7">
          <h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            源文件
            <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-normal text-ink-muted">
              {sources.length}
            </span>
          </h2>
          <div className="card divide-y divide-line/70 overflow-hidden p-0">
            {sources.map((s) => (
              <div key={s.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
                <span className="flex-1 truncate text-ink">{s.filename}</span>
                {s.error && (
                  <span className="hidden max-w-[16rem] truncate text-xs text-red-500 sm:inline" title={s.error}>
                    {s.error}
                  </span>
                )}
                {isBusy(s) ? (
                  <span className="flex items-center gap-1.5 text-xs text-ink-muted">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {ST_LABEL[s.status] ?? s.status}
                  </span>
                ) : (
                  <Badge tone={s.status}>{ST_LABEL[s.status] ?? s.status}</Badge>
                )}
                {!isBusy(s) && (
                  <button
                    type="button"
                    onClick={() => reingest(s.id)}
                    disabled={retrying === s.id}
                    className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-ink-muted transition hover:bg-paper hover:text-accent-dark disabled:opacity-50"
                    title="重新摄入"
                  >
                    <RotateCcw className={`h-3.5 w-3.5 ${retrying === s.id ? "animate-spin" : ""}`} />
                    重新摄入
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

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

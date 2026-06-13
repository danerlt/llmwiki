import { useEffect, useRef, useState, type FormEvent } from "react";
import { FileText, Upload } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken, setToken } from "../api/client";
import type { PageOut, SourceOut } from "../api/types";
import { Badge, EmptyState, PageHeader, Spinner } from "../components/ui";

const PT: Record<string, string> = {
  index: "目录",
  overview: "概览",
  entity: "实体",
  concept: "概念",
  source_summary: "源摘要",
};

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
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

  return (
    <div>
      <PageHeader title="知识库页面" subtitle="上传源文件，LLM 自动编译成带交叉引用的 wiki 页" />
      <form onSubmit={upload} className="card mb-6 flex flex-wrap items-center gap-3 p-4">
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
        <span className="text-xs text-ink-faint">支持 .md / .txt / .pdf</span>
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
        <ul className="card divide-y divide-line overflow-hidden">
          {pages.map((p) => (
            <li key={p.id}>
              <Link
                to={`/pages/${p.id}`}
                className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-paper"
              >
                <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
                <span className="flex-1 truncate text-ink">{p.title}</span>
                <Badge>{PT[p.page_type] ?? p.page_type}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

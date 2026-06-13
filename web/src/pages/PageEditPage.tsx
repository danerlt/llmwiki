import { useEffect, useState, type FormEvent } from "react";
import { Eye, Save, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { apiFetch, del, postJson, putJson } from "../api/client";
import type { PageDetail } from "../api/types";
import Markdown from "../components/Markdown";
import { PageHeader, Spinner } from "../components/ui";

const PAGE_TYPES = [
  { v: "concept", label: "概念" },
  { v: "entity", label: "实体" },
  { v: "overview", label: "概览" },
];

function unwrap(md: string): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, "$1");
}

export default function PageEditPage() {
  const { kbId, pageId } = useParams();
  const isEdit = Boolean(pageId);
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [pageType, setPageType] = useState("concept");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!isEdit) return;
    apiFetch<PageDetail>(`/pages/${pageId}`)
      .then((p) => {
        setTitle(p.title);
        setSlug(p.slug);
        setPageType(PAGE_TYPES.some((t) => t.v === p.page_type) ? p.page_type : "concept");
        setContent(p.content_md);
      })
      .catch(() => setErr("加载页面失败"))
      .finally(() => setLoading(false));
  }, [isEdit, pageId]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setErr("标题不能为空");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      if (isEdit) {
        const p = await putJson<PageDetail>(`/pages/${pageId}`, {
          title,
          content_md: content,
          page_type: pageType,
        });
        navigate(`/pages/${p.id}`);
      } else {
        const p = await postJson<PageDetail>(`/kbs/${kbId}/pages`, {
          title,
          slug: slug.trim() || undefined,
          content_md: content,
          page_type: pageType,
        });
        navigate(`/pages/${p.id}`);
      }
    } catch (e) {
      setErr(e instanceof Error && e.message ? `保存失败：${e.message}` : "保存失败");
      setSaving(false);
    }
  }

  async function remove() {
    if (!confirm("确定删除此页？此操作不可恢复。")) return;
    try {
      const p = await apiFetch<PageDetail>(`/pages/${pageId}`);
      await del(`/pages/${pageId}`);
      navigate(`/kbs/${p.kb_id}/pages`);
    } catch {
      setErr("删除失败");
    }
  }

  if (loading) return <Spinner label="加载中…" />;

  return (
    <div>
      <PageHeader
        title={isEdit ? "编辑页面" : "新建页面"}
        subtitle={isEdit ? "修改后保存会自动留存一个历史版本" : "用 Markdown 撰写，支持 [[wikilink]] 站内链接"}
        action={
          isEdit ? (
            <button onClick={remove} className="btn-ghost text-red-600 hover:bg-red-50">
              <Trash2 className="h-4 w-4" /> 删除
            </button>
          ) : undefined
        }
      />
      <form onSubmit={save} className="space-y-4">
        <div className="flex flex-wrap gap-3">
          <input
            className="field flex-1"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="页面标题"
            autoFocus
          />
          {!isEdit && (
            <input
              className="field w-48"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="slug（留空自动生成）"
            />
          )}
          <select
            className="field w-32"
            value={pageType}
            onChange={(e) => setPageType(e.target.value)}
          >
            {PAGE_TYPES.map((t) => (
              <option key={t.v} value={t.v}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <textarea
            className="field min-h-[28rem] resize-y font-mono text-sm leading-relaxed"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="# 标题&#10;&#10;用 Markdown 写正文，[[其它页]] 可建立站内链接…"
          />
          <div className="card min-h-[28rem] overflow-auto p-6">
            <div className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ink-faint">
              <Eye className="h-3.5 w-3.5" /> 预览
            </div>
            {content.trim() ? (
              <Markdown content={unwrap(content)} />
            ) : (
              <p className="text-sm text-ink-faint">预览将在这里显示…</p>
            )}
          </div>
        </div>

        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex items-center gap-3">
          <button className="btn-primary" disabled={saving}>
            <Save className="h-4 w-4" /> {saving ? "保存中…" : "保存"}
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-ghost"
            disabled={saving}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}

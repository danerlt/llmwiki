import { useEffect, useState, type FormEvent } from "react";
import { MessageSquare, Trash2 } from "lucide-react";

import { apiFetch, del, postJson } from "../api/client";
import type { Comment } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export default function Comments({ pageId }: { pageId: string }) {
  const { user } = useAuth();
  const [items, setItems] = useState<Comment[] | null>(null);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);

  function load() {
    apiFetch<Comment[]>(`/pages/${pageId}/comments`)
      .then(setItems)
      .catch(() => setItems([]));
  }
  useEffect(load, [pageId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setPosting(true);
    try {
      await postJson<Comment>(`/pages/${pageId}/comments`, { body: draft });
      setDraft("");
      load();
    } finally {
      setPosting(false);
    }
  }

  async function remove(id: string) {
    try {
      await del(`/comments/${id}`);
      setItems((prev) => (prev ?? []).filter((c) => c.id !== id));
    } catch {
      /* ignore */
    }
  }

  const canDelete = (c: Comment) => user && (user.id === c.author_id || user.role === "admin");

  return (
    <section className="mt-6">
      <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-ink-faint">
        <MessageSquare className="h-4 w-4" /> 讨论
        {items && items.length > 0 && (
          <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-normal text-ink-muted">
            {items.length}
          </span>
        )}
      </h2>

      <form onSubmit={submit} className="card mb-4 p-3">
        <textarea
          className="field min-h-[4.5rem] resize-y text-sm"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="写下评论，与团队就这页讨论…"
        />
        <div className="mt-2 flex justify-end">
          <button className="btn-primary" disabled={posting || !draft.trim()}>
            {posting ? "发送中…" : "发表评论"}
          </button>
        </div>
      </form>

      {items && items.length > 0 ? (
        <ul className="space-y-3">
          {items.map((c) => (
            <li key={c.id} className="card p-4">
              <div className="mb-1 flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-ink">{c.author_name}</span>
                <span className="flex items-center gap-2 text-xs text-ink-faint">
                  {new Date(c.created_at).toLocaleString()}
                  {canDelete(c) && (
                    <button
                      onClick={() => remove(c.id)}
                      className="text-ink-faint transition hover:text-red-600"
                      title="删除"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-muted">{c.body}</p>
            </li>
          ))}
        </ul>
      ) : (
        items && <p className="text-sm text-ink-faint">还没有评论，来说点什么吧。</p>
      )}
    </section>
  );
}

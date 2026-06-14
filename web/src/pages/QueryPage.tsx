import { useState, type FormEvent } from "react";
import { ChevronDown, Quote, RotateCcw, Sparkles, ThumbsDown, ThumbsUp, User } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch, getToken, postJson, setToken } from "../api/client";
import type { Citation, PageDetail } from "../api/types";
import Markdown from "../components/Markdown";
import { PageHeader, Spinner } from "../components/ui";

const EXAMPLES = ["后端用什么技术栈", "FastAPI 是什么", "知识检索怎么做的"];

interface Turn {
  question: string;
  answer: string;
  citations: Citation[];
  feedback?: "up" | "down";
}

function unwrap(md: string): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, "$1");
}

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [cache, setCache] = useState<Record<string, PageDetail>>({});

  function patchLast(patch: Partial<Turn>) {
    setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, ...patch } : t)));
  }

  async function sendFeedback(ti: number, vote: "up" | "down") {
    const t = turns[ti];
    if (!t || t.feedback) return;
    setTurns((prev) => prev.map((x, i) => (i === ti ? { ...x, feedback: vote } : x)));
    try {
      await postJson("/query/feedback", { question: t.question, answer: t.answer, vote });
    } catch {
      /* 忽略：反馈失败不打扰用户 */
    }
  }

  async function ask(qText: string) {
    if (!qText.trim() || loading || streaming) return;
    const history = turns.flatMap((t) => [
      { role: "user", content: t.question },
      { role: "assistant", content: t.answer },
    ]);
    setQuestion("");
    setLoading(true);
    setTurns((prev) => [...prev, { question: qText, answer: "", citations: [] }]);
    try {
      const res = await fetch("/api/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ question: qText, history }),
      });
      if (res.status === 401) {
        setToken(null);
        location.assign("/login");
        return;
      }
      if (!res.ok || !res.body) {
        patchLast({ answer: "（问答失败，请稍后重试）" });
        return;
      }
      setLoading(false);
      setStreaming(true);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let answer = "";
      let citations: Citation[] = [];
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          if (evt.delta) answer += evt.delta as string;
          if (evt.citations) citations = evt.citations as Citation[];
          patchLast({ answer, citations });
        }
      }
    } catch {
      patchLast({ answer: "（问答失败，请稍后重试）" });
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  }

  function onAsk(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  async function toggle(pageId: string) {
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(pageId)) n.delete(pageId);
      else n.add(pageId);
      return n;
    });
    if (!cache[pageId]) {
      try {
        const p = await apiFetch<PageDetail>(`/pages/${pageId}`);
        setCache((c) => ({ ...c, [pageId]: p }));
      } catch {
        /* 忽略 */
      }
    }
  }

  const busy = loading || streaming;

  return (
    <div>
      <PageHeader
        title="智能问答"
        subtitle="基于你可见知识库作答，可连续追问（带上下文）"
        action={
          turns.length > 0 ? (
            <button onClick={() => setTurns([])} className="btn-ghost" disabled={busy}>
              <RotateCcw className="h-4 w-4" /> 新对话
            </button>
          ) : undefined
        }
      />
      <form onSubmit={onAsk} className="card mb-4 flex items-center gap-2 p-2 pl-4 shadow-lift">
        <Sparkles className="h-5 w-5 shrink-0 text-accent" />
        <input
          className="flex-1 bg-transparent py-2.5 text-base outline-none placeholder:text-ink-faint"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={turns.length ? "继续追问…" : "提个问题，例如「后端用什么技术栈」"}
          autoFocus
        />
        <button className="btn-primary" disabled={busy}>
          {busy ? "生成中…" : turns.length ? "追问" : "提问"}
        </button>
      </form>

      {turns.length === 0 && !busy && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-faint">试试：</span>
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => void ask(q)}
              className="chip transition hover:border-accent/40 hover:text-accent-dark"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-6">
        {turns.map((t, ti) => (
          <div key={ti} className="animate-fade space-y-3">
            <div className="flex items-start gap-2">
              <User className="mt-0.5 h-5 w-5 shrink-0 text-ink-faint" />
              <p className="font-display text-lg font-semibold tracking-tight text-ink">
                {t.question}
              </p>
            </div>
            <div className="card p-6">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-accent">
                <Sparkles className="h-3.5 w-3.5" /> 回答
                {ti === turns.length - 1 && streaming && (
                  <span className="animate-pulse text-ink-faint">生成中…</span>
                )}
              </div>
              {t.answer ? (
                <Markdown content={unwrap(t.answer)} />
              ) : (
                <Spinner label="正在检索并生成…" />
              )}
              {t.answer && !(ti === turns.length - 1 && streaming) && (
                <div className="mt-4 flex items-center gap-2 border-t border-line/70 pt-3 text-xs text-ink-faint">
                  {t.feedback ? (
                    <span>已反馈，谢谢！</span>
                  ) : (
                    <>
                      <span>这个回答有帮助吗？</span>
                      <button
                        onClick={() => void sendFeedback(ti, "up")}
                        className="rounded-lg p-1 transition hover:bg-paper hover:text-accent-dark"
                        title="有帮助"
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => void sendFeedback(ti, "down")}
                        className="rounded-lg p-1 transition hover:bg-paper hover:text-red-600"
                        title="没帮助"
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
            {t.citations.length > 0 && (
              <div>
                <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-ink-muted">
                  <Quote className="h-4 w-4" /> 引用来源
                  <span className="text-xs font-normal text-ink-faint">（点击展开）</span>
                </h3>
                <div className="flex flex-wrap gap-2">
                  {t.citations.map((c) => (
                    <button
                      key={c.page_id}
                      type="button"
                      onClick={() => toggle(c.page_id)}
                      className={`chip transition ${
                        open.has(c.page_id)
                          ? "border-accent/50 bg-accent-soft text-accent-dark"
                          : "hover:border-accent/40 hover:text-accent-dark"
                      }`}
                    >
                      <span className="font-mono text-accent">[{c.index}]</span> {c.title}
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition ${open.has(c.page_id) ? "rotate-180" : ""}`}
                      />
                    </button>
                  ))}
                </div>
                <div className="mt-3 space-y-3">
                  {t.citations
                    .filter((c) => open.has(c.page_id))
                    .map((c) => (
                      <div key={c.page_id} className="card animate-fade p-5">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <span className="font-display text-lg font-semibold tracking-tight">
                            <span className="font-mono text-base text-accent">[{c.index}]</span>{" "}
                            {c.title}
                          </span>
                          <Link
                            to={`/pages/${c.page_id}`}
                            className="shrink-0 text-xs text-accent hover:underline"
                          >
                            查看完整页面 →
                          </Link>
                        </div>
                        {cache[c.page_id] ? (
                          <Markdown content={unwrap(cache[c.page_id].content_md)} />
                        ) : (
                          <Spinner />
                        )}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

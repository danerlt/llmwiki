import { useState, type FormEvent } from "react";
import { Quote, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { postJson } from "../api/client";
import type { AnswerOut } from "../api/types";
import Markdown from "../components/Markdown";
import { PageHeader, Spinner } from "../components/ui";

const EXAMPLES = ["后端用什么技术栈", "FastAPI 是什么", "知识检索怎么做的"];

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [ans, setAns] = useState<AnswerOut | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(qText: string) {
    if (!qText.trim()) return;
    setLoading(true);
    setAns(null);
    try {
      setAns(await postJson<AnswerOut>("/query", { question: qText }));
    } finally {
      setLoading(false);
    }
  }
  function onAsk(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <div>
      <PageHeader title="智能问答" subtitle="基于你可见知识库的内容作答，并给出引用来源" />
      <form onSubmit={onAsk} className="card mb-4 flex items-center gap-2 p-2 pl-4 shadow-lift">
        <Sparkles className="h-5 w-5 shrink-0 text-accent" />
        <input
          className="flex-1 bg-transparent py-2.5 text-base outline-none placeholder:text-ink-faint"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="提个问题，例如「后端用什么技术栈」"
          autoFocus
        />
        <button className="btn-primary" disabled={loading}>
          {loading ? "思考中…" : "提问"}
        </button>
      </form>
      {!ans && !loading && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-faint">试试：</span>
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => {
                setQuestion(q);
                void ask(q);
              }}
              className="chip transition hover:border-accent/40 hover:text-accent-dark"
            >
              {q}
            </button>
          ))}
        </div>
      )}
      {loading && <Spinner label="正在检索并生成回答…" />}
      {ans && (
        <div className="animate-fade space-y-5">
          <div className="card p-6">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-accent">
              <Sparkles className="h-3.5 w-3.5" /> 回答
            </div>
            <Markdown content={ans.answer} />
          </div>
          {ans.citations.length > 0 && (
            <div>
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-ink-muted">
                <Quote className="h-4 w-4" /> 引用来源
              </h2>
              <div className="flex flex-wrap gap-2">
                {ans.citations.map((c) => (
                  <Link
                    key={c.page_id}
                    to={`/pages/${c.page_id}`}
                    className="chip transition hover:border-accent/40 hover:text-accent-dark"
                  >
                    <span className="font-mono text-accent">[{c.index}]</span> {c.title}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

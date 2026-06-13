import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { postJson } from "../api/client";
import type { AnswerOut } from "../api/types";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [ans, setAns] = useState<AnswerOut | null>(null);
  const [loading, setLoading] = useState(false);

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setAns(null);
    try {
      setAns(await postJson<AnswerOut>("/query", { question }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">问答</h1>
      <form onSubmit={onAsk} className="mb-4 flex gap-2">
        <input
          className="flex-1 rounded border px-3 py-2"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="提问（MVP 关键词召回，建议用关键词）"
        />
        <button
          className="rounded bg-slate-800 px-4 text-white hover:bg-slate-700"
          disabled={loading}
        >
          {loading ? "思考中…" : "提问"}
        </button>
      </form>
      {ans && (
        <div className="space-y-4">
          <div className="whitespace-pre-wrap rounded border bg-white p-4">{ans.answer}</div>
          {ans.citations.length > 0 && (
            <div>
              <h2 className="mb-1 text-sm font-semibold text-slate-600">引用</h2>
              <ul className="space-y-1 text-sm">
                {ans.citations.map((c, i) => (
                  <li key={c.page_id}>
                    [{i + 1}]{" "}
                    <Link to={`/pages/${c.page_id}`} className="text-blue-600 hover:underline">
                      {c.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

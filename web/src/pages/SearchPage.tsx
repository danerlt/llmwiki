import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { PageOut } from "../api/types";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PageOut[]>([]);
  const [searched, setSearched] = useState(false);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    setHits(await apiFetch<PageOut[]>(`/search?q=${encodeURIComponent(q)}`));
    setSearched(true);
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">搜索</h1>
      <form onSubmit={onSearch} className="mb-4 flex gap-2">
        <input
          className="flex-1 rounded border px-3 py-2"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="关键词（如：后端）"
        />
        <button className="rounded bg-slate-800 px-4 text-white hover:bg-slate-700">搜索</button>
      </form>
      <ul className="space-y-1">
        {hits.map((p) => (
          <li key={p.id}>
            <Link to={`/pages/${p.id}`} className="text-blue-600 hover:underline">
              {p.title}
            </Link>
            <span className="ml-2 text-xs text-slate-400">[{p.page_type}]</span>
          </li>
        ))}
      </ul>
      {searched && hits.length === 0 && <p className="text-slate-500">无匹配结果</p>}
    </div>
  );
}

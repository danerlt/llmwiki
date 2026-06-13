import { useState, type FormEvent } from "react";
import { FileText, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { PageOut } from "../api/types";
import { Badge, EmptyState, PageHeader } from "../components/ui";

const PT: Record<string, string> = {
  index: "目录",
  overview: "概览",
  entity: "实体",
  concept: "概念",
  source_summary: "源摘要",
};

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PageOut[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    try {
      setHits(await apiFetch<PageOut[]>(`/search?q=${encodeURIComponent(q)}`));
      setSearched(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader title="搜索" subtitle="在你可见的全部知识库中按关键词检索" />
      <form onSubmit={onSearch} className="relative mb-6">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-faint" />
        <input
          className="field !rounded-2xl !py-3.5 !pl-12 !pr-28 text-base"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="输入关键词，如「后端」"
          autoFocus
        />
        <button className="btn-primary absolute right-2 top-1/2 -translate-y-1/2">
          {loading ? "搜索中…" : "搜索"}
        </button>
      </form>
      {searched && hits.length > 0 && (
        <p className="mb-3 text-sm text-ink-muted">找到 {hits.length} 个结果</p>
      )}
      {hits.length > 0 && (
        <ul className="card divide-y divide-line overflow-hidden">
          {hits.map((p) => (
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
      {searched && hits.length === 0 && (
        <EmptyState icon={<Search className="h-8 w-8" />} title="无匹配结果" hint="换个关键词试试。" />
      )}
    </div>
  );
}

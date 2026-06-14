import { useEffect, useRef, useState } from "react";
import { CornerDownLeft, FileText, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { SearchHit } from "../api/types";

const NAV = [
  { label: "概览", to: "/" },
  { label: "搜索", to: "/search" },
  { label: "智能问答", to: "/query" },
  { label: "通知", to: "/notifications" },
  { label: "账号设置", to: "/settings" },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 30);
    else {
      setQ("");
      setHits([]);
    }
  }, [open]);

  useEffect(() => {
    if (!q.trim()) {
      setHits([]);
      return;
    }
    const id = setTimeout(() => {
      apiFetch<SearchHit[]>(`/search?q=${encodeURIComponent(q)}`)
        .then((h) => setHits(h.slice(0, 8)))
        .catch(() => setHits([]));
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  if (!open) return null;

  const navMatches = NAV.filter((n) => !q || n.label.includes(q));

  function go(to: string) {
    setOpen(false);
    navigate(to);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/20 pt-[12vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-card shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search className="h-5 w-5 text-ink-faint" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索页面或跳转…"
            className="flex-1 bg-transparent py-3.5 text-base outline-none placeholder:text-ink-faint"
          />
          <kbd className="rounded bg-paper px-1.5 py-0.5 text-xs text-ink-faint">Esc</kbd>
        </div>
        <div className="max-h-[50vh] overflow-auto p-2">
          {hits.length > 0 && (
            <div className="mb-1 px-2 pt-1 text-xs font-medium uppercase tracking-wider text-ink-faint">
              页面
            </div>
          )}
          {hits.map((h) => (
            <button
              key={h.id}
              onClick={() => go(`/pages/${h.id}`)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-paper"
            >
              <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
              <span className="flex-1 truncate text-ink">{h.title}</span>
            </button>
          ))}
          {navMatches.length > 0 && (
            <div className="mb-1 px-2 pt-2 text-xs font-medium uppercase tracking-wider text-ink-faint">
              跳转
            </div>
          )}
          {navMatches.map((n) => (
            <button
              key={n.to}
              onClick={() => go(n.to)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-paper"
            >
              <CornerDownLeft className="h-4 w-4 shrink-0 text-ink-faint" />
              <span className="flex-1 text-ink">{n.label}</span>
            </button>
          ))}
          {q && hits.length === 0 && navMatches.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-ink-faint">无匹配</p>
          )}
        </div>
      </div>
    </div>
  );
}

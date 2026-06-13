import { useEffect, useState } from "react";
import { ChevronRight, Library } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { KB } from "../api/types";
import { Badge, EmptyState, PageHeader, Spinner } from "../components/ui";

const SCOPE: Record<string, string> = {
  company: "公司",
  department: "部门",
  team: "团队",
  personal: "个人",
};

export default function KbListPage() {
  const [kbs, setKbs] = useState<KB[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<KB[]>("/kbs")
      .then(setKbs)
      .catch(() => setErr("加载知识库失败"));
  }, []);

  return (
    <div>
      <PageHeader title="知识库" subtitle="你有权访问的全部知识库" />
      {err && <p className="text-red-600">{err}</p>}
      {!kbs ? (
        <Spinner />
      ) : kbs.length === 0 ? (
        <EmptyState icon={<Library className="h-8 w-8" />} title="暂无可见知识库" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {kbs.map((kb) => (
            <Link
              key={kb.id}
              to={`/kbs/${kb.id}/pages`}
              className="card group flex items-center gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-lift"
            >
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-dark">
                <Library className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-ink">{kb.name}</div>
                <div className="mt-1.5">
                  <Badge tone={kb.scope_type}>{SCOPE[kb.scope_type] ?? kb.scope_type}</Badge>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-accent" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

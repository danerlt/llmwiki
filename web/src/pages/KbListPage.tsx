import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { KB } from "../api/types";

const SCOPE_LABEL: Record<string, string> = {
  company: "公司",
  department: "部门",
  team: "团队",
  personal: "个人",
};

export default function KbListPage() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<KB[]>("/kbs")
      .then(setKbs)
      .catch(() => setErr("加载 KB 失败"));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">我的知识库</h1>
      {err && <p className="text-red-600">{err}</p>}
      <ul className="space-y-2">
        {kbs.map((kb) => (
          <li key={kb.id}>
            <Link
              to={`/kbs/${kb.id}/pages`}
              className="flex items-center justify-between rounded border bg-white px-4 py-3 hover:bg-slate-50"
            >
              <span className="font-medium">{kb.name}</span>
              <span className="text-xs text-slate-500">
                {SCOPE_LABEL[kb.scope_type] ?? kb.scope_type}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

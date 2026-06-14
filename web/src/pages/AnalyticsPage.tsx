import { useEffect, useState, type ReactNode } from "react";
import { FileWarning, Ghost, ShieldAlert, ThumbsDown, ThumbsUp } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import { PageHeader, Spinner } from "../components/ui";

interface PageBrief {
  id: string;
  title: string;
  updated_at: string | null;
}
interface Analytics {
  feedback: { up: number; down: number };
  stale_days: number;
  stale_pages: PageBrief[];
  orphan_pages: PageBrief[];
  review_due_pages: PageBrief[];
}

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-dark">
        {icon}
      </span>
      <div>
        <div className="font-display text-2xl font-semibold leading-none">{value}</div>
        <div className="mt-1 text-xs text-ink-muted">{label}</div>
      </div>
    </div>
  );
}

function PageList({
  icon,
  title,
  hint,
  pages,
}: {
  icon: ReactNode;
  title: string;
  hint: string;
  pages: PageBrief[];
}) {
  return (
    <section>
      <h2 className="mb-1 flex items-center gap-1.5 font-display text-lg font-semibold tracking-tight">
        {icon} {title}
        <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-normal text-ink-muted">
          {pages.length}
        </span>
      </h2>
      <p className="mb-3 text-xs text-ink-faint">{hint}</p>
      {pages.length === 0 ? (
        <p className="text-sm text-ink-faint">无</p>
      ) : (
        <ul className="card divide-y divide-line overflow-hidden">
          {pages.map((p) => (
            <li key={p.id}>
              <Link
                to={`/pages/${p.id}`}
                className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm transition hover:bg-paper"
              >
                <span className="flex-1 truncate text-ink">{p.title}</span>
                {p.updated_at && (
                  <span className="shrink-0 text-xs text-ink-faint">
                    {new Date(p.updated_at).toLocaleDateString()}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<Analytics>("/analytics")
      .then(setData)
      .catch(() => setErr("加载失败（需要 admin 权限）"));
  }, []);

  if (err) return <p className="text-red-600">{err}</p>;
  if (!data) return <Spinner />;

  const total = data.feedback.up + data.feedback.down;
  const rate = total ? Math.round((data.feedback.up / total) * 100) : 0;

  return (
    <div className="space-y-8">
      <PageHeader title="分析" subtitle="问答满意度与内容健康度，辅助知识治理决策" />
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat icon={<ThumbsUp className="h-5 w-5" />} label="问答点赞" value={data.feedback.up} />
        <Stat icon={<ThumbsDown className="h-5 w-5" />} label="问答点踩" value={data.feedback.down} />
        <Stat
          icon={<ThumbsUp className="h-5 w-5" />}
          label="满意率"
          value={total ? `${rate}%` : "—"}
        />
      </div>
      <div className="grid gap-8 lg:grid-cols-2">
        <PageList
          icon={<FileWarning className="h-4 w-4" />}
          title="陈旧页"
          hint={`超过 ${data.stale_days} 天未更新，建议复审`}
          pages={data.stale_pages}
        />
        <PageList
          icon={<Ghost className="h-4 w-4" />}
          title="孤儿页"
          hint="无任何出链/入链，难被发现，建议补充关联"
          pages={data.orphan_pages}
        />
        <PageList
          icon={<ShieldAlert className="h-4 w-4" />}
          title="待复审"
          hint={`已认证但超过 ${data.stale_days} 天未复核，建议重新认证`}
          pages={data.review_due_pages}
        />
      </div>
    </div>
  );
}

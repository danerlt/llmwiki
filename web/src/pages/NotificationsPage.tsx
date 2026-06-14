import { useEffect, useState } from "react";
import { Bell, Check } from "lucide-react";
import { Link } from "react-router-dom";

import { apiFetch, postJson } from "../api/client";
import type { NotificationItem } from "../api/types";
import { EmptyState, PageHeader, Spinner } from "../components/ui";

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[] | null>(null);

  function load() {
    apiFetch<NotificationItem[]>("/notifications")
      .then(setItems)
      .catch(() => setItems([]));
  }
  useEffect(load, []);

  async function markRead() {
    try {
      await postJson("/notifications/read", {});
      load();
    } catch {
      /* ignore */
    }
  }

  const hasUnread = (items ?? []).some((n) => !n.read);

  return (
    <div>
      <PageHeader
        title="通知"
        subtitle="你关注的页面有编辑或评论时会出现在这里"
        action={
          hasUnread ? (
            <button onClick={markRead} className="btn-ghost">
              <Check className="h-4 w-4" /> 全部标为已读
            </button>
          ) : undefined
        }
      />
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bell className="h-8 w-8" />}
          title="暂无通知"
          hint="在页面右上角点「关注」，该页有更新时你会在此收到提醒。"
        />
      ) : (
        <ul className="card divide-y divide-line overflow-hidden">
          {items.map((n) => (
            <li key={n.id}>
              <Link
                to={n.page_id ? `/pages/${n.page_id}` : "#"}
                className={`flex items-center gap-3 px-4 py-3 text-sm transition hover:bg-paper ${
                  n.read ? "text-ink-muted" : "text-ink"
                }`}
              >
                {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-accent" />}
                <span className="flex-1">{n.message}</span>
                <span className="shrink-0 text-xs text-ink-faint">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

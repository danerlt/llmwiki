const TOKEN_KEY = "llmwiki_token";
const REFRESH_KEY = "llmwiki_refresh";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setRefreshToken(token: string | null): void {
  if (token) localStorage.setItem(REFRESH_KEY, token);
  else localStorage.removeItem(REFRESH_KEY);
}

import type { ApiResponse } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// 业务异常：后端统一信封 success:false 时抛出，带业务 code 与 request_id 供排查
export class BusinessError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public requestId: string | null = null,
  ) {
    super(message);
  }
}

function isEnvelope(p: unknown): p is ApiResponse {
  return (
    typeof p === "object" &&
    p !== null &&
    "success" in p &&
    typeof (p as { success: unknown }).success === "boolean" &&
    "code" in p &&
    "data" in p
  );
}

// 用刷新令牌换新访问令牌；并发去重，避免 401 风暴时重复刷新
let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const r = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!r.ok) return false;
        const d = await r.json();
        setToken(d.access_token);
        if (d.refresh_token) setRefreshToken(d.refresh_token);
        return true;
      } catch {
        return false;
      }
    })();
    void refreshing.finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (res.status === 401) {
    // 访问令牌过期：用刷新令牌静默续期并重试一次
    if (!retried && (await tryRefresh())) {
      return apiFetch<T>(path, init, true);
    }
    setToken(null);
    setRefreshToken(null);
    if (location.pathname !== "/login") location.assign("/login");
    throw new ApiError(401, "unauthorized");
  }
  const ct = res.headers.get("content-type") ?? "";
  const payload = ct.includes("application/json") ? await res.json() : await res.text();
  // 统一信封 {success,code,message,data,request_id}：识别则拆包；未识别则按原行为透传（向后兼容）
  if (isEnvelope(payload)) {
    if (payload.success) return payload.data as T;
    throw new BusinessError(payload.code, payload.message, res.status, payload.request_id ?? null);
  }
  if (!res.ok) {
    throw new ApiError(res.status, typeof payload === "string" ? payload : JSON.stringify(payload));
  }
  return payload as T;
}

export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function putJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function del<T = unknown>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" });
}

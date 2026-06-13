import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiFetch, getToken, setToken } from "../api/client";
import type { UserOut } from "../api/types";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await apiFetch<UserOut>("/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMe();
  }, []);

  async function login(token: string) {
    setToken(token);
    setLoading(true);
    await loadMe();
  }
  async function logout() {
    // 服务端吊销当前会话（自增 token_version），失败也继续清本地，保证总能登出
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      /* best-effort */
    }
    setToken(null);
    setUser(null);
  }

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

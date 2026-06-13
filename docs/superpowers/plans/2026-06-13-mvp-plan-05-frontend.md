# 子计划 5：前端 SPA（React + Vite + TS）— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:executing-plans 逐任务实现。步骤用 `- [ ]` 勾选跟踪。前端测试按 spec §13 从轻：对纯逻辑（api 客户端、wikilink 转换）写 Vitest，组件不强制红绿；每个 Task 跑通后立即提交。

**Goal:** 一个 nginx 托管的 React SPA，覆盖 MVP 前端 8 项中的浏览/检索/上传闭环：登录(JWT) → KB 列表 → wiki 浏览(markdown 渲染 + `[[wikilink]]` 可点击跳转) → 源上传与状态轮询 → 跨可见 KB 关键词搜索 → 引用式问答。打包进 docker-compose（`web` 服务，nginx 反代 `/api` 到 `api:8000`）。

**Architecture:** Vite + React 18 + TypeScript 单页应用。`react-router-dom` 路由；薄 `apiClient`（fetch 封装，自动附 JWT，401 跳登录）；`AuthContext` 管 token（localStorage）；`react-markdown`+`remark-gfm` 渲染，正文里 `[[slug]]` 在渲染前转成指向同 KB 目标页的路由链接。状态用 React hooks，不引状态库。Tailwind 做样式。

**Tech Stack:** Vite、React 18、TypeScript、react-router-dom v6、Tailwind CSS、react-markdown + remark-gfm、Vitest + @testing-library/react。包管理用 **pnpm**。

**Definition of Done:**
- ①`pnpm build` 通过（tsc 无错 + vite 产物）；②`pnpm test` 关键逻辑用例全绿；③`docker compose up` 后 `web`（nginx）可访问，`/api` 反代到后端；④登录→看 KB→浏览页→点 wikilink 跳转→上传→搜索→问答 在浏览器走通（LLM 已配时问答返回带引用答案）。

**约定:** 所有后端调用走相对路径 `/api/...`（由 nginx 反代），开发期用 Vite proxy 同样指向后端，免跨域。

---

## 文件结构（本计划产出）

```
web/
  package.json  pnpm-lock.yaml  tsconfig.json  vite.config.ts
  index.html  postcss.config.js  tailwind.config.js
  Dockerfile  nginx.conf  .dockerignore
  src/
    main.tsx  App.tsx  index.css  vite-env.d.ts
    api/client.ts  api/types.ts
    auth/AuthContext.tsx  auth/ProtectedRoute.tsx
    components/Layout.tsx  components/Markdown.tsx
    lib/wikilink.ts  lib/wikilink.test.ts
    pages/LoginPage.tsx  pages/KbListPage.tsx  pages/KbPagesPage.tsx
    pages/PageDetailPage.tsx  pages/SearchPage.tsx  pages/QueryPage.tsx
  src/api/client.test.ts
docker-compose.yml          # 修改：新增 web 服务
```

> 命令：在 `web/` 下 `pnpm install`、`pnpm build`、`pnpm test`、`pnpm dev`。

---

### Task 1：脚手架（Vite + React + TS + Tailwind + Vitest）

**Files:** `web/package.json`、`web/vite.config.ts`、`web/tsconfig.json`、`web/index.html`、`web/postcss.config.js`、`web/tailwind.config.js`、`web/src/{main.tsx,index.css,vite-env.d.ts}`、`web/.gitignore`

- [ ] **Step 1：`web/package.json`**

```json
{
  "name": "llmwiki-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.0",
    "postcss": "^8.4.41",
    "tailwindcss": "^3.4.10",
    "typescript": "^5.5.4",
    "vite": "^5.4.2",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2：`web/vite.config.ts`**（dev proxy 指向后端 8000；vitest jsdom）

```ts
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
```

- [ ] **Step 3：`web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4：`web/index.html`**

```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>企业 LLM-Wiki</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5：Tailwind 配置**

`web/postcss.config.js`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`web/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

`web/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 6：`web/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 7：`web/src/vite-env.d.ts`** → `/// <reference types="vite/client" />`

- [ ] **Step 8：`web/src/setupTests.ts`** → `import "@testing-library/jest-dom";`

- [ ] **Step 9：临时 `web/src/App.tsx` 占位**（Task 3 替换为真路由）

```tsx
export default function App() {
  return <div className="p-8 text-xl">LLM-Wiki 前端骨架</div>;
}
```

- [ ] **Step 10：`web/.gitignore`** → `node_modules/` 与 `dist/`（根 .gitignore 已含，但 web 内再放一份更清晰）

```
node_modules/
dist/
```

- [ ] **Step 11：安装并验证 build**

Run: `cd web && pnpm install && pnpm build`
Expected: 生成 `web/dist/`，tsc 与 vite 均无错。

- [ ] **Step 12：提交**

```bash
git add web/
git commit -m "feat(web): Vite+React+TS+Tailwind 脚手架（含 Vitest 配置）"
```

---

### Task 2：API 客户端 + 类型（含 Vitest）

**Files:** `web/src/api/types.ts`、`web/src/api/client.ts`、`web/src/api/client.test.ts`

- [ ] **Step 1：`web/src/api/types.ts`**

```ts
export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: string;
  department_id: string | null;
}
export interface KB {
  id: string;
  scope_type: string;
  scope_ref_id: string | null;
  name: string;
}
export interface PageOut {
  id: string;
  kb_id: string;
  title: string;
  slug: string;
  page_type: string;
}
export interface PageDetail extends PageOut {
  content_md: string;
  frontmatter: Record<string, unknown>;
  source_ids: string[];
}
export interface SourceOut {
  id: string;
  kb_id: string;
  filename: string;
  content_type: string;
  status: string;
  error: string | null;
  job_id: string | null;
}
export interface Citation {
  page_id: string;
  title: string;
  kb_id: string;
}
export interface AnswerOut {
  answer: string;
  citations: Citation[];
}
```

- [ ] **Step 2：写失败测试 `web/src/api/client.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getToken, setToken } from "./client";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("attaches bearer token and prefixes /api", async () => {
    setToken("t0ken");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/kbs");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/kbs");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t0ken");
  });

  it("throws ApiError on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("nope", { status: 403 })),
    );
    await expect(apiFetch("/kbs")).rejects.toBeInstanceOf(ApiError);
  });

  it("getToken reflects setToken", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
  });
});
```

- [ ] **Step 3：运行测试，确认失败** —— `cd web && pnpm test`（找不到 ./client 导出）。

- [ ] **Step 4：实现 `web/src/api/client.ts`**

```ts
const TOKEN_KEY = "llmwiki_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (location.pathname !== "/login") location.assign("/login");
    throw new ApiError(401, "unauthorized");
  }
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? await res.json() : (await res.text())) as T;
}

export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 5：运行测试，确认通过**；**Step 6：提交**

```bash
git add web/src/api/
git commit -m "feat(web): apiClient（fetch 封装、JWT 注入、401 跳转）+ 类型 + 测试"
```

---

### Task 3：认证（登录页 + AuthContext + 路由守卫 + 布局）

**Files:** `web/src/auth/AuthContext.tsx`、`web/src/auth/ProtectedRoute.tsx`、`web/src/components/Layout.tsx`、`web/src/pages/LoginPage.tsx`、`web/src/App.tsx`（替换占位）

- [ ] **Step 1：`web/src/auth/AuthContext.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiFetch, getToken, setToken } from "../api/client";
import type { UserOut } from "../api/types";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
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
  function logout() {
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
```

- [ ] **Step 2：`web/src/auth/ProtectedRoute.tsx`**

```tsx
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">加载中…</div>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
```

- [ ] **Step 3：`web/src/pages/LoginPage.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { postJson } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@llmwiki.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await postJson<{ access_token: string }>("/auth/login", { email, password });
      await login(r.access_token);
      navigate("/");
    } catch {
      setErr("登录失败：邮箱或密码错误");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="w-80 space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">企业 LLM-Wiki 登录</h1>
        <input className="w-full rounded border px-3 py-2" value={email}
          onChange={(e) => setEmail(e.target.value)} placeholder="邮箱" />
        <input className="w-full rounded border px-3 py-2" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="w-full rounded bg-slate-800 py-2 text-white hover:bg-slate-700">登录</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 4：`web/src/components/Layout.tsx`**

```tsx
import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <Link to="/" className="font-semibold">LLM-Wiki</Link>
        <Link to="/search" className="text-slate-600 hover:text-slate-900">搜索</Link>
        <Link to="/query" className="text-slate-600 hover:text-slate-900">问答</Link>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-slate-500">{user?.display_name}（{user?.role}）</span>
          <button onClick={logout} className="rounded border px-2 py-1 hover:bg-slate-100">退出</button>
        </div>
      </header>
      <main className="mx-auto max-w-4xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 5：`web/src/App.tsx`（真路由表；引用 Task 4-6 的页面）**

```tsx
import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import KbListPage from "./pages/KbListPage";
import KbPagesPage from "./pages/KbPagesPage";
import LoginPage from "./pages/LoginPage";
import PageDetailPage from "./pages/PageDetailPage";
import QueryPage from "./pages/QueryPage";
import SearchPage from "./pages/SearchPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<KbListPage />} />
            <Route path="/kbs/:kbId/pages" element={<KbPagesPage />} />
            <Route path="/pages/:pageId" element={<PageDetailPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/query" element={<QueryPage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
```

> 注：本 Task 完成后需先建 Task 4-6 的页面占位再能 `pnpm build`；执行时可先建空导出占位，逐 Task 填实。

- [ ] **Step 6：提交**（与 Task 4-6 页面一并 build 通过后提交，或先建占位再提交）

```bash
git add web/src/auth/ web/src/components/Layout.tsx web/src/pages/LoginPage.tsx web/src/App.tsx
git commit -m "feat(web): 认证（AuthContext + 登录页 + 路由守卫 + 布局）"
```

---

### Task 4：KB 列表页

**Files:** `web/src/pages/KbListPage.tsx`

- [ ] **Step 1：实现**

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { KB } from "../api/types";

const SCOPE_LABEL: Record<string, string> = {
  company: "公司", department: "部门", team: "团队", personal: "个人",
};

export default function KbListPage() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<KB[]>("/kbs").then(setKbs).catch(() => setErr("加载 KB 失败"));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">我的知识库</h1>
      {err && <p className="text-red-600">{err}</p>}
      <ul className="space-y-2">
        {kbs.map((kb) => (
          <li key={kb.id}>
            <Link to={`/kbs/${kb.id}/pages`}
              className="flex items-center justify-between rounded border bg-white px-4 py-3 hover:bg-slate-50">
              <span className="font-medium">{kb.name}</span>
              <span className="text-xs text-slate-500">{SCOPE_LABEL[kb.scope_type] ?? kb.scope_type}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2：提交**

```bash
git add web/src/pages/KbListPage.tsx
git commit -m "feat(web): KB 列表页"
```

---

### Task 5：wikilink 转换 + Markdown 组件 + KB 页列表/上传 + 页详情

**Files:** `web/src/lib/wikilink.ts`、`web/src/lib/wikilink.test.ts`、`web/src/components/Markdown.tsx`、`web/src/pages/KbPagesPage.tsx`、`web/src/pages/PageDetailPage.tsx`

- [ ] **Step 1：写失败测试 `web/src/lib/wikilink.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { resolveWikilinks } from "./wikilink";

describe("resolveWikilinks", () => {
  it("turns [[slug]] into markdown link when slug is known", () => {
    const out = resolveWikilinks("见 [[后端]] 和 [[未知]]", {
      后端: "page-1",
    });
    expect(out).toContain("[后端](/pages/page-1)");
    expect(out).toContain("[未知](#)"); // 未命中保留为不可达链接
  });
});
```

- [ ] **Step 2：运行测试确认失败；实现 `web/src/lib/wikilink.ts`**

```ts
/** 把正文里的 [[slug]] 替换为 markdown 链接；slug→pageId 命中时指向 /pages/{id}，否则指向 #。 */
export function resolveWikilinks(md: string, slugToId: Record<string, string>): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, (_m, raw: string) => {
    const slug = raw.trim();
    const id = slugToId[slug];
    return id ? `[${slug}](/pages/${id})` : `[${slug}](#)`;
  });
}
```

- [ ] **Step 3：运行测试确认通过。**

- [ ] **Step 4：`web/src/components/Markdown.tsx`**（react-markdown + 内部链接用 router 跳转）

```tsx
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import remarkGfm from "remark-gfm";

export default function Markdown({ content }: { content: string }) {
  const navigate = useNavigate();
  return (
    <div className="prose max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const to = href ?? "#";
            if (to.startsWith("/")) {
              return (
                <a href={to} className="text-blue-600 underline"
                  onClick={(e) => { e.preventDefault(); navigate(to); }}>
                  {children}
                </a>
              );
            }
            return <a href={to} className="text-blue-600 underline">{children}</a>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 5：`web/src/pages/KbPagesPage.tsx`**（页列表 + 上传 + source 状态轮询）

```tsx
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiFetch, getToken } from "../api/client";
import type { PageOut, SourceOut } from "../api/types";

export default function KbPagesPage() {
  const { kbId = "" } = useParams();
  const [pages, setPages] = useState<PageOut[]>([]);
  const [source, setSource] = useState<SourceOut | null>(null);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  function loadPages() {
    apiFetch<PageOut[]>(`/kbs/${kbId}/pages`).then(setPages).catch(() => setErr("加载页面失败"));
  }
  useEffect(loadPages, [kbId]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/kbs/${kbId}/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    });
    if (!res.ok) { setErr("上传失败（可能无写权限）"); return; }
    const created = (await res.json()) as { source_id: string };
    pollStatus(created.source_id);
  }

  function pollStatus(sourceId: string) {
    const tick = async () => {
      const s = await apiFetch<SourceOut>(`/sources/${sourceId}`);
      setSource(s);
      if (s.status === "pending" || s.status === "processing") {
        setTimeout(tick, 1500);
      } else {
        loadPages(); // done/failed 后刷新页列表
      }
    };
    void tick();
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">知识库页面</h1>
      <form onSubmit={upload} className="mb-6 flex items-center gap-3 rounded border bg-white p-4">
        <input ref={fileRef} type="file" accept=".md,.txt,.pdf" className="text-sm" />
        <button className="rounded bg-slate-800 px-3 py-1 text-white hover:bg-slate-700">上传并摄入</button>
        {source && (
          <span className="text-sm text-slate-600">
            {source.filename}：{source.status}{source.error ? `（${source.error}）` : ""}
          </span>
        )}
      </form>
      {err && <p className="text-red-600">{err}</p>}
      <ul className="space-y-1">
        {pages.map((p) => (
          <li key={p.id}>
            <Link to={`/pages/${p.id}`} className="text-blue-600 hover:underline">
              {p.title} <span className="text-xs text-slate-400">[{p.page_type}]</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 6：`web/src/pages/PageDetailPage.tsx`**（详情 + wikilink 解析）

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { PageDetail, PageOut } from "../api/types";
import Markdown from "../components/Markdown";
import { resolveWikilinks } from "../lib/wikilink";

export default function PageDetailPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [slugMap, setSlugMap] = useState<Record<string, string>>({});

  useEffect(() => {
    apiFetch<PageDetail>(`/pages/${pageId}`).then(async (p) => {
      setPage(p);
      const siblings = await apiFetch<PageOut[]>(`/kbs/${p.kb_id}/pages`);
      setSlugMap(Object.fromEntries(siblings.map((s) => [s.slug, s.id])));
    });
  }, [pageId]);

  if (!page) return <div>加载中…</div>;
  return (
    <article>
      <h1 className="mb-1 text-2xl font-semibold">{page.title}</h1>
      <p className="mb-4 text-xs text-slate-400">{page.page_type} · slug: {page.slug}</p>
      <Markdown content={resolveWikilinks(page.content_md, slugMap)} />
    </article>
  );
}
```

- [ ] **Step 7：提交**

```bash
git add web/src/lib/ web/src/components/Markdown.tsx web/src/pages/KbPagesPage.tsx web/src/pages/PageDetailPage.tsx
git commit -m "feat(web): wikilink 解析 + Markdown 渲染 + KB 页列表/上传 + 页详情"
```

---

### Task 6：搜索页 + 问答页

**Files:** `web/src/pages/SearchPage.tsx`、`web/src/pages/QueryPage.tsx`

- [ ] **Step 1：`web/src/pages/SearchPage.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { PageOut } from "../api/types";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PageOut[]>([]);
  const [searched, setSearched] = useState(false);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    setHits(await apiFetch<PageOut[]>(`/search?q=${encodeURIComponent(q)}`));
    setSearched(true);
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">搜索</h1>
      <form onSubmit={onSearch} className="mb-4 flex gap-2">
        <input className="flex-1 rounded border px-3 py-2" value={q}
          onChange={(e) => setQ(e.target.value)} placeholder="关键词（如：后端）" />
        <button className="rounded bg-slate-800 px-4 text-white hover:bg-slate-700">搜索</button>
      </form>
      <ul className="space-y-1">
        {hits.map((p) => (
          <li key={p.id}>
            <Link to={`/pages/${p.id}`} className="text-blue-600 hover:underline">{p.title}</Link>
            <span className="ml-2 text-xs text-slate-400">[{p.page_type}]</span>
          </li>
        ))}
      </ul>
      {searched && hits.length === 0 && <p className="text-slate-500">无匹配结果</p>}
    </div>
  );
}
```

- [ ] **Step 2：`web/src/pages/QueryPage.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";

import { postJson } from "../api/client";
import type { AnswerOut } from "../api/types";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [ans, setAns] = useState<AnswerOut | null>(null);
  const [loading, setLoading] = useState(false);

  async function onAsk(e: React.FormEvent) {
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
        <input className="flex-1 rounded border px-3 py-2" value={question}
          onChange={(e) => setQuestion(e.target.value)} placeholder="提问（MVP 关键词召回，建议用关键词）" />
        <button className="rounded bg-slate-800 px-4 text-white hover:bg-slate-700" disabled={loading}>
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
                    [{i + 1}] <Link to={`/pages/${c.page_id}`} className="text-blue-600 hover:underline">{c.title}</Link>
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
```

- [ ] **Step 3：`pnpm build` 全量通过 + `pnpm test` 绿；提交**

```bash
git add web/src/pages/SearchPage.tsx web/src/pages/QueryPage.tsx
git commit -m "feat(web): 搜索页 + 引用式问答页"
```

---

### Task 7：Docker 化（nginx 托管 + 反代）+ compose 接入

**Files:** `web/Dockerfile`、`web/nginx.conf`、`web/.dockerignore`、`docker-compose.yml`（修改）

- [ ] **Step 1：`web/nginx.conf`**

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    client_max_body_size 50m;
  }

  location / {
    try_files $uri $uri/ /index.html;   # SPA 路由回退
  }
}
```

- [ ] **Step 2：`web/Dockerfile`（多阶段：pnpm 构建 → nginx 托管）**

```dockerfile
FROM node:24-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3：`web/.dockerignore`** → `node_modules` 与 `dist`

```
node_modules
dist
```

- [ ] **Step 4：改根 `docker-compose.yml` 新增 `web` 服务**（放在 `api` 之后）

```yaml
  web:
    build: ./web
    depends_on: [api]
    ports: ["${WEB_HOST_PORT:-80}:80"]
```

- [ ] **Step 5：提交**

```bash
git add web/Dockerfile web/nginx.conf web/.dockerignore docker-compose.yml
git commit -m "feat(web): nginx 多阶段镜像（反代 /api）+ docker-compose web 服务"
```

---

### Task 8：端到端验证（浏览器闭环）

- [ ] **Step 1：构建并起 web**

Run: `docker compose up -d --build web`
Expected: `web` 容器 Up，`http://localhost:<WEB_HOST_PORT>` 可访问。

- [ ] **Step 2：浏览器闭环**
  - 访问首页 → 跳登录 → 用 `admin@llmwiki.com / admin12345` 登录 → 看到 KB 列表；
  - 进入某 KB → 上传 .md/.txt → 状态轮询到 done（需后端配 LLM；未配则显示 failed + 错误）；
  - 打开生成的页 → markdown 渲染、`[[wikilink]]` 可点击跳转；
  - 搜索关键词 → 命中页可跳转；
  - 问答（LLM 已配时）→ 返回答案 + 引用列表可点击。

- [ ] **Step 3（可选）：Vitest 全绿留档**：`cd web && pnpm test`。

---

## Self-Review（计划自检）

- **Spec 覆盖**：覆盖 spec 第 2.1 的前端相关项——①登录(JWT)、③KB 命名空间浏览、④源上传、⑥Wiki 浏览(markdown + wikilink 跳转)、⑦问答(引用)、⑧关键词搜索；第 3（React+Vite+TS+Tailwind+react-markdown）、第 4（web=nginx 托管 + 反代）、第 10（消费 /auth/login、/me、/kbs、/kbs/{id}/sources、/sources/{id}、/kbs/{id}/pages、/pages/{id}、/search、/query）。✓
  - **未含（MVP 可后补）**：组织管理 admin 界面（建部门/团队/用户）——后端 `/departments`、`/teams`、`/users` 已就绪，前端 admin 面板留作增强；当前用 seed/接口直接管理。
- **占位符扫描**：无 TODO；每步含完整代码。✓
- **类型/命名一致**：`apiFetch/postJson/getToken/setToken/ApiError`、`UserOut/KB/PageOut/PageDetail/SourceOut/AnswerOut/Citation`、`resolveWikilinks(md, slugToId)`、路由 `/`、`/login`、`/kbs/:kbId/pages`、`/pages/:pageId`、`/search`、`/query` 跨 Task 一致。✓
- **依赖顺序**：脚手架→api 客户端→认证/路由→各页面→Docker 单向无环。Task 3 的 App.tsx 引用 Task 4-6 页面，执行时先建占位再填实。✓
- **测试**：按 spec §13 从轻——Vitest 覆盖 `apiClient`（URL/JWT/401）与 `resolveWikilinks`（纯逻辑）；组件以浏览器闭环手测为主。✓

## 执行交接

计划已存 `docs/superpowers/plans/2026-06-13-mvp-plan-05-frontend.md`。按 executing-plans 逐任务实现，每个 Task `pnpm build`/`pnpm test` 通过后立即提交。Task 3 的路由表依赖 Task 4-6 页面，建议执行顺序：Task1 → Task2 → 先建 Task4/5/6 页面（或占位）→ Task3 接线 → Task7/8。

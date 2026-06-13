import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getToken, setToken } from "./client";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("attaches bearer token and prefixes /api", async () => {
    setToken("t0ken");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/kbs");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/kbs");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer t0ken");
  });

  it("throws ApiError on non-2xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 403 })));
    await expect(apiFetch("/kbs")).rejects.toBeInstanceOf(ApiError);
  });

  it("getToken reflects setToken", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
  });
});

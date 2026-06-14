import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, BusinessError, apiFetch, getToken, setToken } from "./client";

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

  it("unwraps unified envelope to data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ success: true, code: "0", message: "ok", data: [{ id: 1 }], request_id: "r" }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    const data = await apiFetch<Array<{ id: number }>>("/kbs");
    expect(data).toEqual([{ id: 1 }]);
  });

  it("throws BusinessError on envelope success:false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ success: false, code: "404", message: "nope", data: null }), {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    await expect(apiFetch("/kbs")).rejects.toBeInstanceOf(BusinessError);
  });

  it("passes through non-envelope JSON (backward compatible)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const data = await apiFetch<{ status: string }>("/health");
    expect(data).toEqual({ status: "ok" });
  });
});

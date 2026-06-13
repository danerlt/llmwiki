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

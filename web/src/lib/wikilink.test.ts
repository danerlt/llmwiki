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

  it("slugifies link text before matching (letters/case/space)", () => {
    // 后端 slug 经归一化：Backend API -> backend-api、概念B -> 概念b
    const out = resolveWikilinks("见 [[Backend API]] 与 [[概念B]]", {
      "backend-api": "p1",
      概念b: "p2",
    });
    expect(out).toContain("[Backend API](/pages/p1)"); // 含字母/空格也能命中
    expect(out).toContain("[概念B](/pages/p2)"); // 大小写归一化后命中，显示保留原文
  });
});

import { describe, expect, it } from "vitest";

import { lineDiff } from "./linediff";

describe("lineDiff", () => {
  it("标注新增、删除与未变行", () => {
    const out = lineDiff("a\nb\nc", "a\nB\nc\nd");
    const types = out.map((l) => `${l.type}:${l.text}`);
    expect(types).toContain("same:a");
    expect(types).toContain("del:b");
    expect(types).toContain("add:B");
    expect(types).toContain("same:c");
    expect(types).toContain("add:d");
  });

  it("内容相同则全部为 same", () => {
    const out = lineDiff("x\ny", "x\ny");
    expect(out.every((l) => l.type === "same")).toBe(true);
  });
});

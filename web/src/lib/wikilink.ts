/** 与后端 api/app/ingest/parser.py:slugify 对齐的归一化：去首尾空白、ASCII 小写、
 *  非字母数字（\p{L}\p{N}_ ≈ Python \w，含 CJK）转连字符。 */
function slugify(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}_]+/gu, "-")
    .replace(/^-+|-+$/g, "");
}

/** 把正文里的 [[原文]] 替换为 markdown 链接：对原文 slugify 后查 slugToId，
 *  命中指向 /pages/{id}，未命中指向 #；显示文本保留原文。 */
export function resolveWikilinks(md: string, slugToId: Record<string, string>): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, (_m, raw: string) => {
    const text = raw.trim();
    const id = slugToId[slugify(raw)];
    return id ? `[${text}](/pages/${id})` : `[${text}](#)`;
  });
}

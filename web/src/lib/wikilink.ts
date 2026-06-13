/** 把正文里的 [[slug]] 替换为 markdown 链接；slug→pageId 命中时指向 /pages/{id}，否则指向 #。 */
export function resolveWikilinks(md: string, slugToId: Record<string, string>): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, (_m, raw: string) => {
    const slug = raw.trim();
    const id = slugToId[slug];
    return id ? `[${slug}](/pages/${id})` : `[${slug}](#)`;
  });
}

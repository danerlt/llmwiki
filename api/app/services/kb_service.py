import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, User
from app.repositories import kb_repo, wiki_repo
from app.schemas.kb import KBOut
from app.services.permission_service import permission_service


class KbService:
    async def list_my_kbs(self, session: AsyncSession, user: User) -> list[KBOut]:
        id_list = list(await permission_service.accessible_kb_ids(session, user))
        kbs = await kb_repo.list_by_ids(session, id_list)
        counts = await wiki_repo.counts_by_kbs(session, id_list)
        return [
            KBOut(
                id=k.id,
                scope_type=k.scope_type,
                scope_ref_id=k.scope_ref_id,
                name=k.name,
                page_count=counts.get(k.id, 0),
            )
            for k in kbs
        ]

    async def ensure_kb(
        self, session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
    ) -> KnowledgeBase:
        existing = await kb_repo.list_by_scope(session, scope_type, scope_ref_id)
        if existing:
            return existing[0]
        return await kb_repo.create(session, scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)

    def _index_markdown(self, pages) -> str:
        """按 page_type 分组列出非 index 页，生成目录 markdown。"""
        groups: dict[str, list] = {}
        for p in pages:
            if p.page_type == "index":
                continue
            groups.setdefault(p.page_type, []).append(p)
        lines = ["# 目录（index）", ""]
        for ptype in ("overview", "entity", "concept", "source_summary"):
            items = groups.get(ptype)
            if not items:
                continue
            lines.append(f"## {ptype}")
            for p in sorted(items, key=lambda x: x.title):
                lines.append(f"- [[{p.slug}]] {p.title}")
            lines.append("")
        return "\n".join(lines)

    async def rebuild_index(self, session: AsyncSession, kb_id: uuid.UUID) -> None:
        """重建某 KB 的 index 目录页（按 page_type 分组列出所有非 index 页）。摄入与晋升共用。"""
        pages = await wiki_repo.list_by_kb(session, kb_id)
        await wiki_repo.upsert(
            session,
            kb_id=kb_id,
            slug="index",
            title="目录",
            page_type="index",
            content_md=self._index_markdown(pages),
            frontmatter={"type": "index"},
            source_ids=[],
        )


kb_service = KbService()

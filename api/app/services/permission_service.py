import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, User, UserTeam
from app.repositories import org_repo


async def accessible_kb_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    ids: set[uuid.UUID] = set()

    res = await session.execute(
        select(KnowledgeBase.id).where(KnowledgeBase.scope_type == "company")
    )
    ids.update(r[0] for r in res.all())

    anc = await org_repo.ancestor_department_ids(session, user.department_id)
    if anc:
        res = await session.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.scope_type == "department",
                KnowledgeBase.scope_ref_id.in_(anc),
            )
        )
        ids.update(r[0] for r in res.all())

    res = await session.execute(select(UserTeam.team_id).where(UserTeam.user_id == user.id))
    team_ids = [r[0] for r in res.all()]
    if team_ids:
        res = await session.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.scope_type == "team",
                KnowledgeBase.scope_ref_id.in_(team_ids),
            )
        )
        ids.update(r[0] for r in res.all())

    res = await session.execute(
        select(KnowledgeBase.id).where(
            KnowledgeBase.scope_type == "personal",
            KnowledgeBase.scope_ref_id == user.id,
        )
    )
    ids.update(r[0] for r in res.all())

    return ids


async def can_write(session: AsyncSession, user: User, kb: KnowledgeBase) -> bool:
    if kb.scope_type == "personal":
        return kb.scope_ref_id == user.id
    if kb.scope_type == "team":
        res = await session.execute(
            select(UserTeam).where(
                UserTeam.user_id == user.id, UserTeam.team_id == kb.scope_ref_id
            )
        )
        return res.first() is not None
    if kb.scope_type in ("department", "company"):
        return user.role == "admin"
    return False

import asyncio

from app.db.session import SessionLocal
from app.ingest import pipeline
from app.repositories import kb_repo, org_repo, user_repo, wiki_repo
from app.services import kb_service, org_service


async def _seed_pages(session, kb_id, items):
    """直接写入示例 wiki 页（无需 LLM），建立链接图与 index 目录。"""
    for it in items:
        p = await wiki_repo.upsert(
            session, kb_id=kb_id, slug=it["slug"], title=it["title"],
            page_type=it["type"], content_md=it["md"], frontmatter={"type": it["type"]}, source_ids=[],
        )
        await session.flush()
        await wiki_repo.replace_links(
            session, from_page_id=p.id, to_slugs=pipeline.extract_wikilinks(it["md"])
        )
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb_id)
    await kb_service.rebuild_index(session, kb_id)


COMPANY_PAGES = [
    {"slug": "公司技术架构概览", "title": "公司技术架构概览", "type": "overview",
     "md": "本公司知识平台后端用 [[FastAPI]] + [[PostgreSQL]]，前端用 [[React]]，"
           "检索走 [[关键词检索]] 与 wikilink 图导航，不使用向量数据库。"},
    {"slug": "FastAPI", "title": "FastAPI", "type": "entity",
     "md": "现代异步 Python Web 框架，承载本平台的 REST 接口，配合 [[PostgreSQL]] 持久化。"},
    {"slug": "PostgreSQL", "title": "PostgreSQL", "type": "entity",
     "md": "主数据库，借助 pg_trgm 扩展支撑 [[关键词检索]] 的子串匹配。"},
    {"slug": "React", "title": "React", "type": "entity",
     "md": "前端 SPA 框架，搭配 Vite 与 Tailwind 构建管理与阅读界面。"},
    {"slug": "关键词检索", "title": "关键词检索", "type": "concept",
     "md": "基于 [[PostgreSQL]] 的关键词召回，叠加共享源与 wikilink 图扩展，按可见知识库过滤。"},
]
TECH_PAGES = [
    {"slug": "研发规范", "title": "研发规范", "type": "overview",
     "md": "分支策略、代码评审、CI 要求。后端实现见 [[后端服务]]。"},
    {"slug": "后端服务", "title": "后端服务", "type": "concept",
     "md": "Controller–Service–Repository 分层；异步 SQLAlchemy；摄入走 arq worker。"},
]
BACKEND_PAGES = [
    {"slug": "接口约定", "title": "接口约定", "type": "concept",
     "md": "统一 REST + JWT 鉴权、错误处理与分页；权限按可见知识库过滤。"},
]


async def seed() -> None:
    async with SessionLocal() as session:
        if await user_repo.get_by_email(session, "admin@llmwiki.com"):
            print("already seeded")
            return
        await kb_service.ensure_kb(session, "company", None, "公司")
        tech = await org_service.create_department(session, name="技术部", parent_id=None)
        backend = await org_service.create_department(session, name="后端组", parent_id=tech.id)
        frontend = await org_service.create_department(session, name="前端组", parent_id=tech.id)
        product = await org_service.create_department(session, name="产品部", parent_id=None)
        admin = await org_service.create_user(
            session, email="admin@llmwiki.com", password="admin12345",
            display_name="管理员", role="admin", department_id=tech.id,
        )
        alice = await org_service.create_user(
            session, email="alice@llmwiki.com", password="alice12345",
            display_name="Alice", role="user", department_id=backend.id,
        )
        await org_service.create_user(
            session, email="bob@llmwiki.com", password="bob12345",
            display_name="Bob", role="user", department_id=frontend.id,
        )
        carol = await org_service.create_user(
            session, email="carol@llmwiki.com", password="carol12345",
            display_name="Carol", role="user", department_id=product.id,
        )
        await session.flush()
        projx = await org_service.create_team(session, name="项目X")
        await session.flush()
        await org_repo.add_team_member(session, team_id=projx.id, user_id=alice.id)
        await org_repo.add_team_member(session, team_id=projx.id, user_id=carol.id)
        _ = admin

        company_kb = (await kb_repo.list_by_scope(session, "company", None))[0]
        tech_kb = (await kb_repo.list_by_scope(session, "department", tech.id))[0]
        backend_kb = (await kb_repo.list_by_scope(session, "department", backend.id))[0]
        await _seed_pages(session, company_kb.id, COMPANY_PAGES)
        await _seed_pages(session, tech_kb.id, TECH_PAGES)
        await _seed_pages(session, backend_kb.id, BACKEND_PAGES)

        await session.commit()
        print("seeded: admin@llmwiki.com / admin12345（含 alice/bob/carol、项目X 团队、示例 wiki 页）")


if __name__ == "__main__":
    asyncio.run(seed())

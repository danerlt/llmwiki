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
    {
        "slug": "公司技术架构概览", "title": "公司技术架构概览", "type": "overview",
        "md": (
            "本平台是一套**会自我维护的企业知识库**：上传的源文件经 LLM 增量编译为带交叉引用的 wiki 页，"
            "检索时沿目录与 [[关键词检索]] 导航，而非每次对原始片段做向量召回。\n\n"
            "## 总体架构\n"
            "- **接入层**：[[React]] 单页应用，经 nginx 反向代理到后端。\n"
            "- **应用层**：[[FastAPI]] 提供 REST 接口，按 Controller–Service–Repository 分层。\n"
            "- **异步层**：[[arq]] worker 消费摄入任务，跑两步 LLM 管线生成页面。\n\n"
            "## 数据与存储\n"
            "- **元数据与全文**：[[PostgreSQL]]（pg_trgm 关键词检索，不引入向量库）。\n"
            "- **对象存储**：[[MinIO]] 保存原始源文件与抽取图片。\n"
            "- **队列**：Redis 承载 arq 任务，保证重启不丢、可重试。\n\n"
            "## 权限与治理\n"
            "知识按 公司 / 部门 / 团队 / 个人 四级作用域隔离；低作用域知识可经审核**晋升**到高作用域，"
            "所有关键操作进入审计日志。"
        ),
    },
    {
        "slug": "fastapi", "title": "FastAPI", "type": "entity",
        "md": (
            "FastAPI 是本平台后端的核心 Web 框架，基于 Starlette 与 Pydantic，原生支持异步。\n\n"
            "## 为什么选它\n"
            "- 异步 I/O 契合摄入/检索中的高并发数据库与 LLM 调用。\n"
            "- Pydantic 模型即请求/响应契约，天然做参数校验与序列化。\n"
            "- 自动生成 OpenAPI 文档，前后端联调成本低。\n\n"
            "## 在本平台的用途\n"
            "承载全部 `/api` 端点：认证、组织管理、知识库、上传、检索问答。控制器保持轻薄，"
            "业务编排在 service 层，数据访问统一走 repository。配合 [[PostgreSQL]] 异步驱动持久化。\n\n"
            "## 关键实践\n"
            "- 依赖注入做鉴权（JWT）与权限校验。\n"
            "- 长耗时的摄入不在请求内同步执行，而是入队交给 [[arq]] worker。"
        ),
    },
    {
        "slug": "postgresql", "title": "PostgreSQL", "type": "entity",
        "md": (
            "PostgreSQL 是本平台的主数据库，存储用户、组织、知识库、wiki 页与链接图等全部元数据。\n\n"
            "## 关键词检索\n"
            "启用 `pg_trgm` 扩展，对页面标题与正文建 GIN trgm 索引，支撑中文子串匹配，"
            "作为 [[关键词检索]] 的底层召回手段——无需引入向量数据库。\n\n"
            "## 数据模型要点\n"
            "- `wiki_pages`：按 `(kb_id, slug)` 唯一，存正文、frontmatter、来源 id。\n"
            "- `page_links`：解析 `[[wikilink]]` 得到的有向边，命中既有页时回填目标。\n"
            "- 迁移由 Alembic 管理，schema 变更可回滚。\n\n"
            "## 运维\n"
            "容器化部署，数据卷持久化；生产建议开启定期备份与连接池监控。"
        ),
    },
    {
        "slug": "react", "title": "React", "type": "entity",
        "md": (
            "React 是本平台前端框架，搭配 Vite 构建、TypeScript 类型、Tailwind 设计系统。\n\n"
            "## 技术栈\n"
            "- 路由：react-router；状态：组件 hooks（不引重型状态库）。\n"
            "- 渲染：react-markdown 精排 wiki 正文，`[[wikilink]]` 解析为可点击跳转。\n"
            "- 鉴权：JWT 存本地，apiClient 统一注入并处理 401。\n\n"
            "## 界面约定\n"
            "侧边栏外壳 + 主内容区；列表、卡片、徽章、空态、加载态统一组件化，"
            "与 [[FastAPI]] 暴露的接口一一对应。"
        ),
    },
    {
        "slug": "关键词检索", "title": "关键词检索", "type": "concept",
        "md": (
            "本平台不使用向量/RAG，而是把知识编译成结构化页面，检索时**沿结构导航**。\n\n"
            "## 召回策略\n"
            "1. **按词召回**：把查询切成 ASCII 词与中文相邻二元组，分别在 [[PostgreSQL]] 上做子串匹配，按命中词数排序。\n"
            "2. **图扩展**：从种子页沿 `[[wikilink]]` 与共享源拉入相关页。\n"
            "3. **目录地图**：附上各知识库的 index 目录，给 LLM 一张全局图。\n\n"
            "## 权限铁律\n"
            "所有结果在进入上下文或返回前，**严格按调用者可见知识库过滤**——平级部门、他人个人库的内容绝不外泄。\n\n"
            "## 局限与展望\n"
            "中文目前用 trgm 子串兜底，未来可接入 zhparser 分词与 tsvector 排序进一步提升相关性。"
        ),
    },
]
TECH_PAGES = [
    {
        "slug": "研发规范", "title": "研发规范", "type": "overview",
        "md": (
            "技术部统一的研发流程与质量基线，新成员入职必读。\n\n"
            "## 分支与提交\n"
            "- 主干保护，功能走特性分支，经评审合并。\n"
            "- 提交信息说明「为何改」，关联任务编号。\n\n"
            "## 测试与 CI\n"
            "- 后端遵循 TDD：先写失败测试，再最小实现（见 [[后端服务]]）。\n"
            "- 每次提交须通过全部测试与格式检查，CI 红则不合并。\n\n"
            "## 数据库变更\n"
            "schema 变更一律用 `alembic revision` 生成迁移骨架后填写 upgrade/downgrade，不手写整文件。"
        ),
    },
    {
        "slug": "后端服务", "title": "后端服务", "type": "concept",
        "md": (
            "后端采用清晰的分层架构，依赖方向单向收敛。\n\n"
            "## 分层\n"
            "- **Controller**：HTTP 入口，薄；只做校验、调 service、返回 schema。\n"
            "- **Service**：业务编排与事务；权限集中在 `permission_service`。\n"
            "- **Repository**：封装全部 SQLAlchemy 查询，其它层不直接碰库。\n\n"
            "## 摄入管线\n"
            "上传 → 入队 → worker 取文件 → 解析 → 两步 LLM（分析→生成）→ 落 wiki 页（带溯源）→ "
            "写链接图 → 重建目录。失败置 failed 可观测、可重试。\n\n"
            "## 鉴权与权限\n"
            "JWT 鉴权 + 四级作用域权限；写权限：个人本人、团队成员、部门/公司管理员。"
        ),
    },
]
BACKEND_PAGES = [
    {
        "slug": "接口约定", "title": "接口约定", "type": "concept",
        "md": (
            "后端组对外 REST 接口的统一约定。\n\n"
            "## 风格\n"
            "- 资源名词复数，动作用 HTTP 方法表达；路径前缀 `/api`。\n"
            "- 请求/响应均为 JSON，由 Pydantic 模型定义契约。\n\n"
            "## 鉴权与错误\n"
            "- 除登录外均需 `Authorization: Bearer <jwt>`。\n"
            "- 统一错误码：401 未认证、403 越权、404 不存在、422 参数错误。\n\n"
            "## 分页与过滤\n"
            "列表接口默认限量返回，检索类结果**始终按调用者可见知识库过滤**（见 [[后端服务]]）。"
        ),
    },
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
        await org_service.create_user(
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

        company_kb = (await kb_repo.list_by_scope(session, "company", None))[0]
        tech_kb = (await kb_repo.list_by_scope(session, "department", tech.id))[0]
        backend_kb = (await kb_repo.list_by_scope(session, "department", backend.id))[0]
        await _seed_pages(session, company_kb.id, COMPANY_PAGES)
        await _seed_pages(session, tech_kb.id, TECH_PAGES)
        await _seed_pages(session, backend_kb.id, BACKEND_PAGES)

        await session.commit()
        print("seeded: admin@llmwiki.com / admin12345（含 alice/bob/carol、项目X 团队、丰富示例 wiki 页）")


if __name__ == "__main__":
    asyncio.run(seed())

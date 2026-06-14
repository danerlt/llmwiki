# Lumen Agent 操作指南（自主开发循环用，保持精简）

> 本文件是"循环工程（Loop Engineering）"的操作记忆层之一。每轮全新上下文的 agent
> 都应先读本文件，再读 `IMPLEMENTATION_PLAN.md`（任务队列）与 `docs/`（需求真相源）。

## 门禁命令（提交前必须全绿，已核实可用）

- 后端测试：`cd api && uv run pytest`          # pyproject: testpaths=["tests"], asyncio_mode=auto
- 前端测试：`cd web && pnpm test`               # vitest run（注意：本项目用 pnpm@10，不是 npm）
- 前端类型：`cd web && pnpm exec tsc --noEmit`  # tsc 即类型门禁
- 后端 lint：（暂无 ruff/black/mypy，requirements.txt 未引入 —— 引入工具后再补此行，勿编造）

## 数据库变更（红线，不可违反）

- 禁止手写 Alembic 迁移文件。必须先
  `cd api && uv run alembic revision -m "..."`（必要时加 `--autogenerate`）生成骨架，
  再在生成的文件里填写 upgrade()/downgrade() 正文。让 Alembic 生成 revision id / down_revision 链。

## 约定

- commit message、日志、注释用中文；代码标识符（类名/函数名/Literal）保持英文。
- 一轮只做一件事，做完原子提交（中文 message，说明"为何"改）。
- 改前先用并行 subagent 搜索代码库确认未实现，别假设（don't assume not implemented）。
- 永不禁用/跳过测试来"让它过"——修测试或修实现。
- build/test 只用 1 个 subagent（多了会回压崩溃）；文件搜索可并行。

## 安全作业区（关键）

- 只许动 `IMPLEMENTATION_PLAN.md` 末尾"可继续自主推进（无外部依赖）"区的任务。
- 一旦命中"需老板拍板才能落地（阻塞）"区（向量/混合检索、SSO/SCIM、多租户隔离），
  立即停止并输出 `<promise>NEEDS_BOSS</promise>`，说明卡在哪、需要什么决策。

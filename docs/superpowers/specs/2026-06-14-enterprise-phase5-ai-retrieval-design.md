# 阶段 5：AI 与检索升级 — as-built 设计文档

> 状态：as-built（已上线）· 日期：2026-06-14 · 方法论：superpowers（回溯补档）
> 对应 IMPLEMENTATION_PLAN 阶段 5 · 关联提交：
> - `dcd3eef` feat(ai): SSE 流式问答——回答边生成边显示，结束附引用
> - `28c5f85` docs(plan): 阶段5 SSE流式问答完成标记
> - `855d639` feat(ai): 多轮对话问答（追问带上下文）+ 前端对话流式界面
> - `a3eacef` docs(plan): 标记评论/标签/多轮对话完成
> - `b99e7f9` feat(ai): 问答答案反馈（赞/踩）闭环 —— 度量与迭代 AI 质量
> - `e3b23d5` docs(plan): 标记答案反馈完成
> - （前置）`39e8a05` feat(query): query_service 组装编号上下文 + LLM 生成 + 引用；`4eccd45` feat(query): 引用来源优化——剔除目录页、只列答案真正引用的来源
>
> 说明：本组功能先开发后补档，本 spec 记录"实际建成"的设计与取舍（非事前计划）。

---

## 1. 背景与目标

企业采购知识库问答产品时，把"问答体验是否对标商业 AI 助手"当作硬性验收项：能否像 ChatGPT 那样**边生成边显示**（避免十几秒空等）、能否**连续追问**（沿上下文对话而非每次从零）、能否**沉淀用户反馈**用于迭代质量。MVP 阶段（见 `2026-06-13-enterprise-llm-wiki-mvp-design.md`）已交付"权限感知的关键词+图导航检索 + 一次性引用回答"，但回答是**整段阻塞返回**、**单轮无记忆**、**无反馈通道**。

阶段 5 的目标是"从关键词召回向语义/混合检索演进，问答体验对标商业产品"。本阶段**实际建成**的是其中"问答交互体验"这一子集：SSE 流式问答、多轮对话上下文、答案赞/踩反馈闭环（记录 + 聚合）。检索底层仍沿用 MVP 的关键词召回 + 图扩展，未引入向量/混合检索（原因见第 9 节）。

本文档只描述**已经建成并上线**的实现。

---

## 2. 范围

对照 IMPLEMENTATION_PLAN 阶段 5。

### ✅ 已建成

| 能力 | 实现落点 |
| --- | --- |
| SSE 流式问答（回答逐 token 推送，结束推送引用来源） | `controllers/query.py` 的 `POST /query/stream`、`services/query_service.py:answer_stream`、`integrations/llm.py:LLMClient.stream`、前端 `pages/QueryPage.tsx` |
| 多轮对话（追问携带会话上下文） | `schemas/query.py:ChatTurn/QueryRequest.history`、`query_service` 透传 `history`、`LLMClient._messages` 拼接历史消息、前端 `QueryPage` 累积 `turns` 并回传 |
| 答案反馈赞/踩（逐条记录 + 按 vote 聚合） | `models/answer_feedback.py`、`repositories/feedback_repo.py`、`POST /query/feedback`，聚合经 `GET /analytics` 暴露 |

### ⬜ 明确未做（阶段 5 内仍待办）

- ⬜ **查询改写**（query rewrite）：检索仍直接用原始问题切词。
- ⬜ **向量嵌入基础设施**：embedding 服务 + pgvector 向量存储 + 增量更新（因 DeepSeek 无 embedding 接口阻塞，见第 9 节）。
- ⬜ **混合检索**：trgm/BM25 + 向量 → rerank。
- ⬜ **片段级溯源 + 置信度 + 防幻觉 grounding 校验**：当前引用是**页面级**（整页编号），非片段级；无置信度评分、无独立 grounding 校验环节（仅靠 system prompt 约束"只依据给定资料、不足就说不知道"）。
- ⬜ **摄入期自动富集**：本阶段不涉及。

---

## 3. 架构与关键设计决策

### 3.1 分层落点

```
前端 QueryPage.tsx
   │  POST /api/query/stream  (fetch + ReadableStream 手动解析 SSE)
   ▼
controllers/query.py        ── FastAPI StreamingResponse(media_type="text/event-stream")
   │  注入 get_current_user / get_db / get_llm
   ▼
services/query_service.py   ── _prepare 检索+组编号资料 → answer_stream 逐块产出 SSE 帧
   │
   ├── services/retrieval_service.py   ── 权限感知关键词召回 + 图扩展（沿用 MVP）
   └── integrations/llm.py:LLMClient   ── OpenAI 兼容 chat/completions，stream=True 逐 token

反馈链路：
QueryPage → POST /api/query/feedback → controllers/query.py
            → repositories/feedback_repo.create（写 answer_feedback）
            → services/audit_service.record（审计 action="answer.feedback"）
聚合：GET /api/analytics → feedback_repo.counts（group by vote）
```

### 3.2 关键决策：SSE 用 FastAPI `StreamingResponse` + 手写 `data:` 帧（不引第三方库）

- **服务端**：`controllers/query.py:query_stream` 直接返回 `fastapi.responses.StreamingResponse`，`media_type="text/event-stream"`，并显式带 `Cache-Control: no-cache` 与 `X-Accel-Buffering: no`（关闭 Nginx 等反代缓冲，确保逐块直达浏览器）。**未引入 `sse-starlette` / `EventSourceResponse`**，遵循"不无故引新工具"。
- **帧格式**：`query_service._sse(obj)` 把 dict 序列化为标准 SSE 帧 `data: <json>\n\n`（`ensure_ascii=False` 保留中文，`default=str` 兜底 UUID 等非 JSON 原生类型）。
- **两类事件**（无显式 `event:` 字段，全部走默认 message，由 payload 字段区分）：
  - 增量帧：`{"delta": "<文本片段>"}` —— 逐 token 推送回答。
  - 结束帧：`{"done": true, "citations": [...]}` —— 流末尾一次性附引用来源。
- **降级**：`answer_stream` 内对 `llm.stream(...)` 包 try/except，流中断时补发一条 `{"delta": "\n\n（问答服务中断，请稍后重试）", "done": true, "citations": []}` 收尾，绝不向客户端抛裸异常（呼应"不静默吞异常但也不裸 500"）。
- **无资料短路**：检索 `_prepare` 返回 `None`（可见 KB 无相关非 index 页）时，先发一条 `{"delta": _NO_CONTEXT}` 再发 `{"done": true, "citations": []}`，**不调用 LLM**（省成本、防幻觉）。

LLM 客户端侧（`LLMClient.stream`）以 `httpx.AsyncClient.stream("POST", ...)` 发起带 `stream: true` 的请求，逐行 `aiter_lines()` 解析上游 OpenAI 风格 `data:` 行：跳过非 `data:` 行、遇 `[DONE]` 终止、解析 `choices[0].delta.content` 并仅在非空时 `yield`。流式响应无 `usage` 回传，故 `metrics.observe_llm(0)` 仅计调用次数。

### 3.3 关键决策：多轮上下文走"客户端持有全量历史、每次请求回传"

- **无服务端会话存储**：没有 conversation/session 表，避免引入会话生命周期、过期清理等状态管理复杂度。前端 `QueryPage` 在内存 `turns` 数组中累积每轮 `{question, answer, citations}`，下一次提问时 `flatMap` 展开为 `[{role:"user",...},{role:"assistant",...}, ...]` 作为 `history` 回传。
- **请求契约**：`QueryRequest.history: list[ChatTurn] | None`，`ChatTurn.content` 限长 8000 字符，`history` 最多 20 轮（`max_length=20`）—— 在边界处约束上下文体积，防止放大下游 token 成本。
- **拼接位置**：`LLMClient._messages(system, user, history)` 把历史插在 `system` 之后、当前 `user` 之前，并对每条做白名单校验（`role ∈ {user, assistant}` 且 `content` 为非空 str）才放行，丢弃畸形项。
- **`/query` 与 `/query/stream` 同源**：两个端点共用同一 `history` 透传路径与 `_prepare` 逻辑，仅产出形态不同（整段 vs 流式），保证行为一致。

### 3.4 关键决策：引用为"页面级编号 + 答案回采过滤"

- `query_service._prepare` 把检索到的非 `index` 页编号为 `[1]..[n]`，每页正文截断到 `_PAGE_CHAR_BUDGET=2000` 字符塞进 user prompt，并构造候选 `citations`（`index/page_id/title/kb_id`）。
- system prompt（`QUERY_SYSTEM`）要求模型"每条事实句末用 `[n]` 标注来源、方括号只用于来源编号、资料不足就说不知道"。
- `_filter_citations` 用正则 `\[(\d+)\]` 扫描答案实际引用到的编号，只回传被引用的来源；模型完全未标注时回退展示全部（避免空引用列表）。
- `_WIKILINK` 正则把答案里残留的 `[[X]]` 去壳为 `X`（前端答案区按纯文本/Markdown 渲染，双链语法无意义）。

### 3.5 关键决策：反馈写入复用审计基线，聚合复用 analytics 端点

- 反馈记录走独立表 `answer_feedback`，但**不引新控制器**：写入挂在已有 `query` 控制器下（`POST /query/feedback`），聚合读取挂在已有 `analytics` 控制器下（`GET /analytics`），与"内容健康"指标（陈旧页/孤儿页/待复审）并列成一块管理员质量看板。
- 写入时同步调 `audit_service.record(action="answer.feedback", target_type="query", detail={"vote": ...})`，纳入统一审计流。

---

## 4. 数据模型变更

### 4.1 新增表 `answer_feedback`

迁移文件：`api/migrations/versions/aa979a660c35_add_answer_feedback_table.py`
（revision `aa979a660c35`，down_revision `b17ca4b2da9b`）

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `Uuid` | PK，默认 `uuid4()` | 主键 |
| `user_id` | `Uuid` | NOT NULL，FK → `users.id` | 反馈提交者 |
| `question` | `Text` | NOT NULL | 被评价的问题原文 |
| `answer` | `Text` | NOT NULL | 被评价的答案原文 |
| `vote` | `String(8)` | NOT NULL，索引 `ix_answer_feedback_vote` | 取值 `"up"` / `"down"` |
| `created_at` | `DateTime(timezone=True)` | NOT NULL，`server_default=now()` | 提交时间 |

模型定义：`api/app/models/answer_feedback.py:AnswerFeedback`。

> 设计取舍：表中直接冗余存 `question`/`answer` 全文（而非外键关联某条"回答记录"），因为问答本身无持久化记录（答案是流式即时生成、不落库），反馈需自带评价对象的快照才有分析价值。`vote` 建索引以支撑按投票方向 group by 聚合。

> 阶段 5 内仅此一张新表，无对既有表的字段增改。

---

## 5. API 端点

所有端点挂在 `prefix="/api"`（见 `main.py`），均要求登录。

| 方法 | 路径 | 控制器 | 鉴权/权限 | 说明 |
| --- | --- | --- | --- | --- |
| `POST` | `/api/query/stream` | `query.query_stream` | `get_current_user`（登录用户） | SSE 流式问答；返回 `text/event-stream`，逐帧 `{delta}`，末帧 `{done, citations}` |
| `POST` | `/api/query` | `query.query` | `get_current_user`（登录用户） | 非流式问答；返回 `AnswerOut{answer, citations}`，支持 `history` 多轮 |
| `POST` | `/api/query/feedback` | `query.query_feedback` | `get_current_user`（登录用户） | 记录答案赞/踩，`201 Created`，返回 `{"ok": true}` |
| `GET` | `/api/analytics` | `analytics.analytics` | `require_admin`（仅管理员） | 管理员看板，`feedback` 字段含 `{up, down}` 聚合 + 内容健康指标 |

请求/响应 schema（`api/app/schemas/query.py`）：

- `QueryRequest`：`question`(1–2000 字)、`kb_scope: list[UUID] | None`、`history: list[ChatTurn] | None`（≤20 轮）。
- `ChatTurn`：`role`、`content`（≤8000 字）。
- `FeedbackRequest`：`question`(1–2000)、`answer`(1–20000)、`vote: Literal["up","down"]`。
- `AnswerOut`：`answer`、`citations: list[Citation]`；`Citation`：`index/page_id/title/kb_id`。

> `/query` 与 `/query/feedback` 端点本体由 MVP/前置提交建立，本阶段为其新增 `history` 多轮能力与 `/query/stream` 流式变体、`/query/feedback` 反馈通道。

---

## 6. 权限与安全不变量

- **检索结果绝不越权**：流式与非流式问答均经 `retrieval_service.retrieve` → `permission_service.accessible_kb_ids(user)` 过滤，返回集合中每页 `kb_id` 必属用户可见 KB（铁律）。`kb_scope` 仅能在可见集合内**收窄**（取交集），不能扩权。
- **引用只来自可见 KB**：`citations` 由检索结果派生，故末帧附带的来源编号同样受权限约束。测试 `test_query_stream_emits_deltas_and_citations` 断言平级部门 KB 的 `kb_id` 不出现在引用中。
- **输入边界防成本放大**：`question ≤ 2000`、`history ≤ 20 轮`、单轮 `content ≤ 8000`，在 schema 校验层（422）拦截，避免向下游 LLM 透传超大上下文。
- **反馈写入需登录**：`POST /query/feedback` 要求 `get_current_user`，`vote` 用 `Literal` 限定，非法值（如 `"meh"`）在 422 拒绝。
- **聚合看板限管理员**：`/analytics` 路由级 `dependencies=[Depends(require_admin)]`，普通用户无法读取满意度聚合。
- **降级不泄露内部错误**：LLM 不可用/流中断时返回中文降级文案，不透出堆栈或上游错误细节。

---

## 7. 配置项

阶段 5 未新增环境变量；流式问答复用 MVP 既有的 LLM 配置（`api/app/core/config.py`）：

| 配置项 | 默认值 | 含义 |
| --- | --- | --- |
| `llm_base_url` | `""` | OpenAI 兼容 chat/completions 的 base URL（如 DeepSeek） |
| `llm_api_key` | `""` | LLM API key（`Authorization: Bearer` 注入） |
| `llm_model` | `""` | 模型名（流式与非流式共用） |

`controllers/query.py:get_llm()` 以这三项构造 `LLMClient`。`LLMClient` 另有进程内默认（非环境变量）：`timeout=120s`、`max_retries=2`、`backoff_base=0.5`、`temperature=0`；流式请求额外带 `stream: true`。

---

## 8. 测试覆盖

| 测试文件 | 关键用例 | 验证点 |
| --- | --- | --- |
| `api/tests/test_api_search_query.py` | `test_query_stream_emits_deltas_and_citations` | SSE 端点返回 `text/event-stream`；拼接所有 `delta` 还原答案；末帧 `done` 带 `citations`；引用只含可见 KB |
| `api/tests/test_api_search_query.py` | `test_query_feedback_recorded` | 赞/踩写入后 `feedback_repo.counts` 计数为 1；非法 `vote` 返回 422 |
| `api/tests/test_api_search_query.py` | `test_query_returns_answer_and_citations` | 非流式问答返回答案含 `[1]`、引用仅来自可见 KB |
| `api/tests/test_api_search_query.py` | `test_query_rejects_overlong_question` | 超长问题（>2000）在边界 422 拒绝 |
| `api/tests/test_query_service.py` | `test_answer_assembles_context_and_returns_citations` | 组装编号资料、回传带编号的引用、user prompt 含 `[1]` |
| `api/tests/test_query_service.py` | `test_answer_empty_when_no_pages` | 无资料时不调用 LLM、引用为空 |
| `api/tests/test_query_service.py` | `test_answer_degrades_when_llm_fails` | LLM 抛错时降级返回"暂不可用"而非裸 500，仍带可见 KB 引用 |
| `api/tests/test_query_service.py` | `test_answer_strips_wikilink_syntax` | 答案中 `[[X]]` 去壳为 `X`，文字保留 |
| `api/tests/test_retrieval_service.py` | `test_retrieve_never_returns_inaccessible_kb` | 检索铁律：平级部门 KB 不可见、本部门可见 |
| `api/tests/test_retrieval_service.py` | `test_graph_expansion_pulls_linked_pages` | 图扩展拉入直接链接页（即便不含关键词） |
| `api/tests/test_retrieval_service.py` | `test_retrieve_caps_result_and_prioritizes_seed` | 结果受 limit≤8 约束、关键词种子优先保留 |
| `api/tests/test_retrieval_service.py` | `test_retrieve_handles_natural_language_question` | 自然语言整句按词召回（python/后端）而非整串子串 |

测试用 `tests.fakes.FakeLLM` 替身（其 `stream` 逐字产出、`complete` 返回预置答案），并通过 `app.dependency_overrides[query_ctrl.get_llm]` 注入，无需真实 LLM。

---

## 9. 已知限制与未来工作

对照 roadmap 阶段 5 的 ⬜ 项：

- **检索仍是关键词召回 + 图扩展**：`retrieval_service` 用 ASCII 词 + 中文相邻二元组切词，无语义理解；自然语言长问题靠"按词召回多词命中排序"兜底，召回质量天花板有限。
- **向量/混合检索缺位（阻塞项）**：DeepSeek 无 embedding 接口。需老板二选一——(A) 接 OpenAI/智谱等 embedding API（需 key + 成本）；(B) 本地 sentence-transformers（引入 ~2GB torch，镜像与内存显著变重）。方案未定，故 pgvector/embedding 基础设施、BM25/trgm+向量+rerank 混合检索均未动工。
- **查询改写未做**：未引入"问题 → 检索友好查询"的改写环节。
- **溯源为页面级、无 grounding 校验**：引用是整页编号，非片段级；无置信度评分；防幻觉仅靠 system prompt 约束，无独立的"答案是否被资料支撑"的程序化校验。
- **多轮上下文无服务端持久化**：会话历史完全由前端内存持有，刷新页面即丢失；也无法跨设备续聊。当前为简化取舍，若需会话持久化/共享需新增会话存储。
- **流式无 token 计量**：上游流式响应不回传 `usage`，`metrics` 仅能记调用次数，流式问答的 token 成本暂不可观测（非流式 `/query` 仍记 `total_tokens`）。

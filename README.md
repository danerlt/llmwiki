# 企业 LLM-Wiki（MVP）

基于 Karpathy 的 LLM-Wiki 模式的企业知识库：LLM 把上传的源文件增量编译成带交叉引用的结构化 wiki，查询时沿"目录 + wikilink + 关键词"导航（非向量 RAG）。详见 `docs/superpowers/specs/`。

## 本地启动
```bash
cp .env.example .env   # 按需填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
docker compose up -d --build
curl localhost:8000/api/health   # -> {"status":"ok"}
```

## 后端测试
```bash
cd api && pip install -r requirements.txt && pytest -q
```

## 架构
- 后端 FastAPI（Controller–Service–Repository 分层）+ PostgreSQL(pg_trgm) + Redis(arq worker) + MinIO
- 前端 React + Vite + TypeScript
- LLM：OpenAI 兼容接口（可配），仅文本生成

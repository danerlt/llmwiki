FROM python:3.12-slim

# 从官方镜像复制 uv 二进制（无需 curl 安装脚本）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# 依赖层：仅 pyproject.toml / uv.lock 变更时才重装（最大化层缓存）
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

# 代码层（.dockerignore 已排除 .venv / tests / 缓存）
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

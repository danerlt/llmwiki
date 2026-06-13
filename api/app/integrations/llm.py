import asyncio

import httpx

from app.core import metrics

# 可重试的瞬时网络错误（连接/读写超时、连接中断等）
_RETRIABLE_EXC = (httpx.TimeoutException, httpx.TransportError)


class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端（仅文本生成，无 embedding）。

    内置健壮化：可配超时；对瞬时网络错误与 429/5xx 做指数退避重试；4xx 客户端错误不重试；
    记录调用次数与 token 用量到 metrics（成本可观测）。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120,
        max_retries: int = 2,
        backoff_base: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._transport = transport

    async def complete(self, system: str, user: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._call(system, user)
            except _RETRIABLE_EXC as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code != 429 and code < 500:
                    raise  # 4xx（鉴权/请求错误）重试无意义，立即抛
                last_exc = exc
            if attempt < self.max_retries:
                await asyncio.sleep(self.backoff_base * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def _call(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            metrics.observe_llm(usage.get("total_tokens") or 0)
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = None
            if not isinstance(content, str):
                raise ValueError(f"LLM 返回结构异常: {str(data)[:200]}")
            return content

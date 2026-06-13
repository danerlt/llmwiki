import httpx


class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端（仅文本生成，无 embedding）。"""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
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
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = None
            if not isinstance(content, str):
                raise ValueError(f"LLM 返回结构异常: {str(data)[:200]}")
            return content

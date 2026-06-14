"""测试用内存 Fake：不连真 LLM / MinIO。"""


class FakeStorage:
    """内存对象存储，实现 StorageBackend 接口。"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return f"memory://{key}"


class FakeLLM:
    """按调用顺序返回预设响应；记录收到的 prompt 便于断言。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str, history=None) -> str:
        self.calls.append((system, user))
        self.history = history
        return self._responses.pop(0) if self._responses else ""

    async def stream(self, system: str, user: str, history=None):
        """逐字 yield 预设响应，模拟流式输出。"""
        self.calls.append((system, user))
        self.history = history
        text = self._responses.pop(0) if self._responses else ""
        for ch in text:
            yield ch

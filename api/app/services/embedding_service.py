"""本地 sentence-transformers 文本向量化（语义检索）。

设计为可降级：未装 sentence-transformers 或 EMBEDDINGS_ENABLED=false 时，embed() 返回 None，
检索退回纯关键词路径——保证测试与轻量部署无需 torch 依赖。
"""

import logging

from app.core.config import settings

_logger = logging.getLogger("app.embedding")


class EmbeddingService:
    """向量化单例：惰性加载模型（实例内缓存），不可用即降级。"""

    def __init__(self) -> None:
        self._model = None
        self._load_failed = False

    def enabled(self) -> bool:
        return settings.embeddings_enabled

    def _get_model(self):
        if self._model is not None or self._load_failed:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embeddings_model)
        except Exception:  # noqa: BLE001 — 缺依赖/加载失败则降级关闭
            self._load_failed = True
            _logger.warning("sentence-transformers 不可用，向量检索降级为关键词检索")
        return self._model

    def embed(self, text: str) -> list[float] | None:
        """返回归一化向量（便于用点积当余弦）；未启用/不可用/空文本时返回 None。"""
        if not settings.embeddings_enabled or not text or not text.strip():
            return None
        model = self._get_model()
        if model is None:
            return None
        vec = model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vec]

    def cosine(self, a: list[float], b: list[float]) -> float:
        """两个归一化向量的余弦相似度（即点积）。"""
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b, strict=False))


embedding_service = EmbeddingService()

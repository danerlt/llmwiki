from app.services import embedding_service


def test_cosine_of_normalized_vectors():
    assert embedding_service.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert embedding_service.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert embedding_service.cosine([], [1.0]) == 0.0  # 维度不匹配/空 → 0


def test_embed_disabled_returns_none(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "embeddings_enabled", False)
    assert embedding_service.embed("任意文本") is None  # 关闭时不依赖 torch

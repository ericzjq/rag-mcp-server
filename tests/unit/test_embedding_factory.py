"""
Embedding 工厂单元测试：Fake embedding 返回稳定向量，工厂按 provider 分流。
"""

from typing import Any, List, Optional

import pytest

from core.settings import (
    EmbeddingSettings,
    EvaluationSettings,
    LlmSettings,
    ObservabilitySettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    SplitterSettings,
    VectorStoreSettings,
)
from libs.embedding.base_embedding import BaseEmbedding
from libs.embedding.embedding_factory import create, register_embedding_provider


def _make_settings(
    embedding_provider: str = "openai",
    embedding_model: str = "text-embedding-3-small",
) -> Settings:
    """构建用于测试的 Settings（含指定 embedding.provider）。"""
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider=embedding_provider, model=embedding_model),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class FakeEmbedding(BaseEmbedding):
    """测试用 Fake Embedding：固定返回稳定向量（固定维度、可复现）。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        # 稳定向量：第 i 段文本对应 [i+1, 2, 3, 4]，便于断言且无浮点误差
        return [[float(i + 1), 2.0, 3.0, 4.0] for i in range(len(texts))]


def test_fake_embedding_returns_stable_vectors() -> None:
    """Fake embedding 返回稳定、可复现的向量。"""
    register_embedding_provider("fake", FakeEmbedding)
    try:
        settings = _make_settings(embedding_provider="fake")
        emb = create(settings)
        assert isinstance(emb, FakeEmbedding)
        vectors = emb.embed(["a", "b", "c"], trace=None)
        assert len(vectors) == 3
        assert vectors[0] == [1.0, 2.0, 3.0, 4.0]
        assert vectors[1] == [2.0, 2.0, 3.0, 4.0]
        assert vectors[2] == [3.0, 2.0, 3.0, 4.0]
    finally:
        from libs.embedding import embedding_factory

        embedding_factory._PROVIDERS.pop("fake", None)


def test_factory_unknown_provider_raises() -> None:
    """未知 provider 时抛出 ValueError，错误信息包含 provider 名称。"""
    settings = _make_settings(embedding_provider="unknown_embed")
    with pytest.raises(ValueError) as exc_info:
        create(settings)
    assert "unknown_embed" in str(exc_info.value)
    assert "Unknown Embedding provider" in str(exc_info.value)


def test_factory_routing_by_provider() -> None:
    """不同 provider 路由到不同实现，返回不同向量。"""
    class StubA(BaseEmbedding):
        def __init__(self, settings: Settings) -> None:
            pass
        def embed(self, texts: List[str], trace: Optional[Any] = None) -> List[List[float]]:
            return [[1.0] * 2 for _ in texts]

    class StubB(BaseEmbedding):
        def __init__(self, settings: Settings) -> None:
            pass
        def embed(self, texts: List[str], trace: Optional[Any] = None) -> List[List[float]]:
            return [[2.0] * 2 for _ in texts]

    register_embedding_provider("stub_a", StubA)
    register_embedding_provider("stub_b", StubB)
    try:
        a = create(_make_settings(embedding_provider="stub_a"))
        b = create(_make_settings(embedding_provider="stub_b"))
        assert a.embed(["x"]) == [[1.0, 1.0]]
        assert b.embed(["x"]) == [[2.0, 2.0]]
    finally:
        from libs.embedding import embedding_factory

        embedding_factory._PROVIDERS.pop("stub_a", None)
        embedding_factory._PROVIDERS.pop("stub_b", None)

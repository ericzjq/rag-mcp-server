"""
VectorStore 契约测试：约束 BaseVectorStore 的输入输出 shape。
"""

from typing import Any, Dict, List, Optional

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
from libs.vector_store.base_vector_store import (
    BaseVectorStore,
    QueryResultItem,
    VectorStoreRecord,
)
from libs.vector_store.vector_store_factory import create, register_vector_store_provider


def _make_settings(vector_store_provider: str = "chroma") -> Settings:
    """构建用于测试的 Settings。"""
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(
            provider=vector_store_provider,
            persist_directory="data/chroma",
        ),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class FakeVectorStore(BaseVectorStore):
    """内存 Fake，用于契约测试：约束 upsert/query 的输入输出 shape。"""

    def __init__(self, settings: Settings) -> None:
        self._store: Dict[str, VectorStoreRecord] = {}

    def upsert(
        self,
        records: List[VectorStoreRecord],
        trace: Optional[Any] = None,
    ) -> None:
        for r in records:
            assert "id" in r and "vector" in r and "metadata" in r
            assert isinstance(r["id"], str)
            assert isinstance(r["vector"], list) and all(isinstance(x, (int, float)) for x in r["vector"])
            assert isinstance(r["metadata"], dict)
            self._store[r["id"]] = dict(r)

    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        trace: Optional[Any] = None,
    ) -> List[QueryResultItem]:
        assert isinstance(vector, list)
        assert isinstance(top_k, int) and top_k >= 0
        # 简单返回：按 id 顺序取前 top_k 条，score 固定 1.0（契约只约束 shape）
        items = []
        for i, (vid, rec) in enumerate(list(self._store.items())[:top_k]):
            items.append({"id": vid, "score": 1.0, "metadata": rec.get("metadata", {})})
        return items


def test_upsert_record_shape() -> None:
    """upsert 接受的 record 必须含 id、vector、metadata。"""
    register_vector_store_provider("fake", FakeVectorStore)
    try:
        store = create(_make_settings(vector_store_provider="fake"))
        store.upsert([
            {"id": "a", "vector": [0.1, 0.2], "metadata": {"source": "doc1"}},
        ], trace=None)
    finally:
        from libs.vector_store import vector_store_factory
        vector_store_factory._PROVIDERS.pop("fake", None)


def test_query_return_shape() -> None:
    """query 返回的每项必须含 id、score，可选 metadata。"""
    register_vector_store_provider("fake", FakeVectorStore)
    try:
        store = create(_make_settings(vector_store_provider="fake"))
        store.upsert([
            {"id": "x", "vector": [1.0, 0.0], "metadata": {}},
        ], trace=None)
        results = store.query([1.0, 0.0], top_k=5, filters=None, trace=None)
        assert isinstance(results, list)
        for item in results:
            assert "id" in item and "score" in item
            assert isinstance(item["id"], str)
            assert isinstance(item["score"], (int, float))
    finally:
        from libs.vector_store import vector_store_factory
        vector_store_factory._PROVIDERS.pop("fake", None)


def test_factory_unknown_provider_raises() -> None:
    """未知 provider 时抛出 ValueError。"""
    with pytest.raises(ValueError) as exc_info:
        create(_make_settings(vector_store_provider="unknown_vs"))
    assert "unknown_vs" in str(exc_info.value)
    assert "Unknown VectorStore provider" in str(exc_info.value)

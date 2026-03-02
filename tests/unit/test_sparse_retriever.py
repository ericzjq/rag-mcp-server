"""
SparseRetriever 单元测试（D3）：BM25 查询 + get_by_ids 合并，返回完整 text 与 metadata。
"""

from typing import Any, List, Optional
from unittest.mock import MagicMock

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
from core.types import RetrievalResult
from core.query_engine.sparse_retriever import SparseRetriever
from ingestion.storage.bm25_indexer import BM25Indexer
from libs.vector_store.base_vector_store import BaseVectorStore


def _make_settings() -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class _MockBM25Indexer(BM25Indexer):
    """返回预设 (chunk_id, score) 列表。"""

    def __init__(self, id_scores: List[tuple]) -> None:
        super().__init__(index_dir="")
        self._id_scores = id_scores

    def query_with_scores(self, terms: List[str], top_k: int = 10) -> List[tuple]:
        return self._id_scores[:top_k]


class _MockVectorStore(BaseVectorStore):
    def __init__(self, records: Optional[List[dict]] = None) -> None:
        self._by_id = {r["id"]: r for r in (records or [])}

    def upsert(self, records: List[Any], trace: Optional[Any] = None) -> None:
        pass

    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[dict] = None,
        trace: Optional[Any] = None,
    ) -> List[dict]:
        return []

    def get_by_ids(self, ids: List[str]) -> List[dict]:
        return [
            {"id": i, "text": self._by_id.get(i, {}).get("text", ""), "metadata": self._by_id.get(i, {}).get("metadata", {})}
            for i in ids
        ]


def test_retrieve_returns_full_text_and_metadata() -> None:
    """返回结果包含完整 text 与 metadata。"""
    bm25 = _MockBM25Indexer(id_scores=[("c1", 0.9), ("c2", 0.5)])
    store = _MockVectorStore(records=[
        {"id": "c1", "text": "First chunk text.", "metadata": {"source_path": "a.pdf"}},
        {"id": "c2", "text": "Second chunk.", "metadata": {}},
    ])
    retriever = SparseRetriever(_make_settings(), bm25_indexer=bm25, vector_store=store)
    results = retriever.retrieve(["hello", "world"], top_k=5)
    assert len(results) == 2
    assert results[0].chunk_id == "c1" and results[0].score == 0.9
    assert results[0].text == "First chunk text."
    assert results[0].metadata == {"source_path": "a.pdf"}
    assert results[1].chunk_id == "c2" and results[1].text == "Second chunk."


def test_retrieve_empty_keywords_returns_empty() -> None:
    """空 keywords 返回空列表。"""
    retriever = SparseRetriever(_make_settings(), bm25_indexer=_MockBM25Indexer([]), vector_store=_MockVectorStore())
    assert retriever.retrieve([], top_k=5) == []


def test_retrieve_preserves_bm25_order() -> None:
    """结果顺序与 BM25 分数顺序一致。"""
    bm25 = _MockBM25Indexer(id_scores=[("b", 0.8), ("a", 0.7)])
    store = _MockVectorStore(records=[{"id": "a", "text": "A", "metadata": {}}, {"id": "b", "text": "B", "metadata": {}}])
    retriever = SparseRetriever(_make_settings(), bm25_indexer=bm25, vector_store=store)
    results = retriever.retrieve(["x"], top_k=10)
    assert [r.chunk_id for r in results] == ["b", "a"]

"""
DenseRetriever 单元测试（D2）：mock EmbeddingClient 与 VectorStore，编排调用与返回格式。
"""

from typing import Any, Dict, List, Optional

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
from core.query_engine.dense_retriever import DenseRetriever
from libs.embedding.base_embedding import BaseEmbedding
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


class _MockEmbedding(BaseEmbedding):
    def __init__(self, dim: int = 4) -> None:
        self._dim = dim

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]


class _MockVectorStore(BaseVectorStore):
    def __init__(self, results: Optional[List[Dict[str, Any]]] = None) -> None:
        self._results = results or []

    def upsert(self, records: List[Any], trace: Optional[Any] = None) -> None:
        pass

    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        trace: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        return self._results[:top_k]

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        by_id = {r["id"]: r for r in self._results}
        return [{"id": i, "text": by_id.get(i, {}).get("text", ""), "metadata": by_id.get(i, {}).get("metadata", {})} for i in ids if i in by_id]


def test_retrieve_returns_retrieval_results_with_chunk_id_score_text_metadata() -> None:
    """返回结果包含 chunk_id、score、text、metadata。"""
    store = _MockVectorStore(results=[
        {"id": "c1", "score": 0.9, "text": "First chunk.", "metadata": {"source_path": "a.pdf"}},
        {"id": "c2", "score": 0.7, "text": "Second chunk.", "metadata": {}},
    ])
    retriever = DenseRetriever(
        _make_settings(),
        embedding_client=_MockEmbedding(dim=4),
        vector_store=store,
    )
    results = retriever.retrieve("hello", top_k=5, trace=None)
    assert len(results) == 2
    assert results[0].chunk_id == "c1"
    assert results[0].score == 0.9
    assert results[0].text == "First chunk."
    assert results[0].metadata == {"source_path": "a.pdf"}
    assert results[1].chunk_id == "c2"
    assert results[1].text == "Second chunk."


def test_retrieve_empty_query_returns_empty_list() -> None:
    """空 query 返回空列表。"""
    retriever = DenseRetriever(_make_settings(), embedding_client=_MockEmbedding(), vector_store=_MockVectorStore())
    assert retriever.retrieve("", top_k=5) == []
    assert retriever.retrieve("   ", top_k=5) == []


def test_retrieval_result_serializable() -> None:
    """RetrievalResult 可 to_dict / from_dict。"""
    r = RetrievalResult(chunk_id="x", score=0.5, text="t", metadata={"k": "v"})
    d = r.to_dict()
    assert d["chunk_id"] == "x" and d["score"] == 0.5 and d["text"] == "t" and d["metadata"] == {"k": "v"}
    r2 = RetrievalResult.from_dict(d)
    assert r2.chunk_id == r.chunk_id and r2.score == r.score and r2.text == r.text

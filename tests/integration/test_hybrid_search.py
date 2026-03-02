"""
HybridSearch 集成测试（D5）：Top-K 含 chunk 文本与 metadata；filters；Dense/Sparse 单路降级。
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
from core.query_engine.dense_retriever import DenseRetriever
from core.query_engine.hybrid_search import HybridSearch
from core.query_engine.query_processor import QueryProcessor
from core.query_engine.sparse_retriever import SparseRetriever


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


def _result(cid: str, score: float = 0.5, text: str = "", metadata: dict = None) -> RetrievalResult:
    return RetrievalResult(chunk_id=cid, score=score, text=text or f"text_{cid}", metadata=metadata or {})


class _MockDenseRetriever(DenseRetriever):
    def __init__(self, results: List[RetrievalResult]) -> None:
        super().__init__(_make_settings(), embedding_client=MagicMock(), vector_store=MagicMock())
        self._results = results

    def retrieve(self, query: str, top_k: int, filters: Optional[dict] = None, trace: Optional[Any] = None) -> List[RetrievalResult]:
        return self._results[:top_k]


class _MockSparseRetriever(SparseRetriever):
    def __init__(self, results: List[RetrievalResult]) -> None:
        super().__init__(_make_settings(), bm25_indexer=MagicMock(), vector_store=MagicMock())
        self._results = results

    def retrieve(self, keywords: List[str], top_k: int, trace: Optional[Any] = None) -> List[RetrievalResult]:
        return self._results[:top_k]


def test_hybrid_search_returns_top_k_with_text_and_metadata() -> None:
    """能返回 Top-K，包含 chunk 文本与 metadata。"""
    dense = _MockDenseRetriever([_result("c1", 0.9, "Dense chunk.", {"source_path": "a.pdf"})])
    sparse = _MockSparseRetriever([_result("c2", 0.8, "Sparse chunk.", {"source_path": "b.pdf"})])
    hybrid = HybridSearch(_make_settings(), dense_retriever=dense, sparse_retriever=sparse)
    results = hybrid.search("test query", top_k=5)
    assert len(results) <= 5
    assert len(results) >= 1
    for r in results:
        assert r.chunk_id and r.text is not None and isinstance(r.metadata, dict)


def test_hybrid_search_metadata_filters() -> None:
    """支持 filters 参数进行后置过滤。"""
    dense = _MockDenseRetriever([
        _result("c1", 0.9, "A", {"collection": "X"}),
        _result("c2", 0.8, "B", {"collection": "Y"}),
    ])
    sparse = _MockSparseRetriever([])
    hybrid = HybridSearch(_make_settings(), dense_retriever=dense, sparse_retriever=sparse)
    results = hybrid.search("q", top_k=10, filters={"collection": "X"})
    assert all(r.metadata.get("collection") == "X" for r in results)
    assert len(results) <= 1


def test_hybrid_search_fallback_when_sparse_fails() -> None:
    """Sparse 失败时降级到仅 Dense 结果。"""
    dense = _MockDenseRetriever([_result("d1", 0.9, "Only dense.")])
    class _FailingSparse(SparseRetriever):
        def __init__(self) -> None:
            super().__init__(_make_settings(), bm25_indexer=MagicMock(), vector_store=MagicMock())
        def retrieve(self, keywords: List[str], top_k: int, trace: Optional[Any] = None) -> List[RetrievalResult]:
            raise RuntimeError("sparse failed")
    hybrid = HybridSearch(_make_settings(), dense_retriever=dense, sparse_retriever=_FailingSparse())
    results = hybrid.search("q", top_k=5)
    assert len(results) >= 1
    assert results[0].chunk_id == "d1" and results[0].text == "Only dense."


def test_query_trace_contains_stages_and_trace_type() -> None:
    """一次查询生成 trace，包含 query_processing/dense_retrieval/sparse_retrieval/fusion/rerank，trace_type=query。"""
    from core.trace.trace_context import TraceContext
    from core.query_engine.reranker import Reranker

    dense = _MockDenseRetriever([_result("c1", 0.9, "Dense.")])
    sparse = _MockSparseRetriever([_result("c2", 0.8, "Sparse.")])
    settings = _make_settings()
    hybrid = HybridSearch(settings, dense_retriever=dense, sparse_retriever=sparse)
    mock_backend = MagicMock()
    mock_backend.rerank = lambda query, candidates, trace=None: list(candidates)
    reranker = Reranker(settings, backend=mock_backend)
    trace = TraceContext(trace_type="query")

    results = hybrid.search("test", top_k=5, trace=trace)
    results = reranker.rerank("test", results, trace=trace)
    trace.finish()

    d = trace.to_dict()
    assert d["trace_type"] == "query"
    stages = d["stages"]
    assert "query_processing" in stages
    assert "dense_retrieval" in stages
    assert "sparse_retrieval" in stages
    assert "fusion" in stages
    assert "rerank" in stages
    for name in ("query_processing", "dense_retrieval", "sparse_retrieval", "fusion", "rerank"):
        assert "elapsed_ms" in stages[name]
        assert "method" in stages[name]

"""
BatchProcessor 单元测试（C10）：batch_size=2 时 5 chunks 分成 3 批，顺序稳定；记录批次耗时。
"""

from typing import Any, List, Optional

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
from core.trace.trace_context import TraceContext
from core.types import Chunk, ChunkRecord
from ingestion.embedding.batch_processor import BatchProcessor
from ingestion.embedding.dense_encoder import DenseEncoder
from ingestion.embedding.sparse_encoder import SparseEncoder
from libs.embedding.base_embedding import BaseEmbedding


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


def _chunk(text: str, chunk_id: str) -> Chunk:
    return Chunk(id=chunk_id, text=text, metadata={})


class _MockEmbedding(BaseEmbedding):
    def __init__(self, dim: int = 4) -> None:
        self._dim = dim

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]


def test_batch_size_2_five_chunks_three_batches_stable_order() -> None:
    """batch_size=2 时对 5 chunks 分成 3 批，且顺序稳定。"""
    from libs.embedding.embedding_factory import create as create_embedding
    settings = _make_settings()
    dense = DenseEncoder(settings, embedding_client=_MockEmbedding(dim=4))
    sparse = SparseEncoder()
    processor = BatchProcessor(settings, dense_encoder=dense, sparse_encoder=sparse)
    chunks = [
        _chunk("a", "c1"),
        _chunk("b", "c2"),
        _chunk("c", "c3"),
        _chunk("d", "c4"),
        _chunk("e", "c5"),
    ]
    records = processor.process(chunks, batch_size=2, trace=None)
    assert len(records) == 5
    assert [r.id for r in records] == ["c1", "c2", "c3", "c4", "c5"]
    for r in records:
        assert r.dense_vector is not None
        assert len(r.dense_vector) == 4
        assert r.sparse_vector is not None
        assert isinstance(r.sparse_vector, dict)


def test_batch_timings_recorded_to_trace() -> None:
    """提供 trace 时记录 batch_timings。"""
    settings = _make_settings()
    dense = DenseEncoder(settings, embedding_client=_MockEmbedding(dim=2))
    processor = BatchProcessor(settings, dense_encoder=dense, sparse_encoder=SparseEncoder())
    chunks = [_chunk("x", "c1"), _chunk("y", "c2")]
    trace = TraceContext()
    records = processor.process(chunks, batch_size=2, trace=trace)
    assert len(records) == 2
    timings = trace.get_stage("batch_timings")
    assert timings is not None
    assert len(timings) == 1
    assert "batch_index" in timings[0] and "elapsed_sec" in timings[0]


def test_empty_chunks_returns_empty() -> None:
    """空 chunks 返回空列表。"""
    settings = _make_settings()
    processor = BatchProcessor(settings)
    assert processor.process([], batch_size=2, trace=None) == []


def test_single_batch() -> None:
    """单批：batch_size 大于等于 len(chunks) 时一批完成。"""
    settings = _make_settings()
    dense = DenseEncoder(settings, embedding_client=_MockEmbedding(dim=2))
    processor = BatchProcessor(settings, dense_encoder=dense, sparse_encoder=SparseEncoder())
    chunks = [_chunk("a", "c1")]
    records = processor.process(chunks, batch_size=10, trace=None)
    assert len(records) == 1
    assert records[0].id == "c1"
    assert records[0].dense_vector is not None
    assert records[0].sparse_vector == {"a": 1.0}

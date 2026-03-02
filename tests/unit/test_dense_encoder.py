"""
DenseEncoder 单元测试（C8）：输出向量数量与 chunks 一致，维度一致。
"""

from typing import Any, List, Optional
from unittest.mock import MagicMock

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
from core.types import Chunk, ChunkRecord
from ingestion.embedding.dense_encoder import DenseEncoder
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


def _chunk(text: str, chunk_id: str = "c1") -> Chunk:
    return Chunk(id=chunk_id, text=text, metadata={})


class _MockEmbedding(BaseEmbedding):
    """返回固定维度的 mock 向量，数量与输入 texts 一致。"""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]


def test_dense_encoder_output_count_and_dimension() -> None:
    """Encoder 输出向量数量与 chunks 一致，维度一致。"""
    dim = 384
    mock_emb = _MockEmbedding(dim=dim)
    encoder = DenseEncoder(_make_settings(), embedding_client=mock_emb)
    chunks = [
        _chunk("first", "c1"),
        _chunk("second", "c2"),
        _chunk("third", "c3"),
    ]
    records = encoder.encode(chunks, trace=None)
    assert len(records) == len(chunks)
    for i, r in enumerate(records):
        assert isinstance(r, ChunkRecord)
        assert r.id == chunks[i].id
        assert r.text == chunks[i].text
        assert r.dense_vector is not None
        assert len(r.dense_vector) == dim
        assert r.sparse_vector is None
    # 所有向量维度相同
    dims = [len(r.dense_vector) for r in records if r.dense_vector]
    assert len(set(dims)) == 1 and dims[0] == dim


def test_dense_encoder_empty_chunks() -> None:
    """空 chunks 返回空列表。"""
    mock_emb = _MockEmbedding(dim=8)
    encoder = DenseEncoder(_make_settings(), embedding_client=mock_emb)
    records = encoder.encode([], trace=None)
    assert records == []


def test_dense_encoder_preserves_metadata() -> None:
    """ChunkRecord 保留 Chunk 的 metadata。"""
    mock_emb = _MockEmbedding(dim=4)
    encoder = DenseEncoder(_make_settings(), embedding_client=mock_emb)
    chunks = [Chunk(id="c1", text="x", metadata={"source_path": "a.pdf", "page": 1})]
    records = encoder.encode(chunks, trace=None)
    assert len(records) == 1
    assert records[0].metadata == {"source_path": "a.pdf", "page": 1}


def test_dense_encoder_raises_on_length_mismatch() -> None:
    """embed 返回数量与 chunks 不一致时抛出 ValueError。"""
    mock_emb = MagicMock(spec=BaseEmbedding)
    mock_emb.embed.return_value = [[0.0, 0.0]]  # 只返回 1 个向量，chunks 有 2 个
    encoder = DenseEncoder(_make_settings(), embedding_client=mock_emb)
    chunks = [_chunk("a", "c1"), _chunk("b", "c2")]
    with pytest.raises(ValueError, match="向量数.*与 chunks 数.*不一致"):
        encoder.encode(chunks, trace=None)


def test_dense_encoder_raises_on_dimension_mismatch() -> None:
    """embed 返回的向量维度不一致时抛出 ValueError。"""
    mock_emb = MagicMock(spec=BaseEmbedding)
    mock_emb.embed.return_value = [[0.0, 0.0], [0.0, 0.0, 0.0]]  # 维度不同
    encoder = DenseEncoder(_make_settings(), embedding_client=mock_emb)
    chunks = [_chunk("a", "c1"), _chunk("b", "c2")]
    with pytest.raises(ValueError, match="向量维度不一致"):
        encoder.encode(chunks, trace=None)

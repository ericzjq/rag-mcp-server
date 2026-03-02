"""
SparseEncoder 单元测试（C9）：输出结构可用于 bm25_indexer；对空文本有明确行为。
"""

from typing import Any, Optional

import pytest

from core.types import Chunk, ChunkRecord
from ingestion.embedding.sparse_encoder import SparseEncoder, _term_frequencies, _tokenize


def _chunk(text: str, chunk_id: str = "c1") -> Chunk:
    return Chunk(id=chunk_id, text=text, metadata={})


def test_sparse_encoder_output_structure_for_bm25_indexer() -> None:
    """输出为 ChunkRecord 列表，含 sparse_vector Dict[str, float]，可供 bm25_indexer 使用。"""
    encoder = SparseEncoder()
    chunks = [
        _chunk("hello world hello", "c1"),
        _chunk("world foo", "c2"),
    ]
    records = encoder.encode(chunks, trace=None)
    assert len(records) == 2
    for i, r in enumerate(records):
        assert isinstance(r, ChunkRecord)
        assert r.id == chunks[i].id
        assert r.text == chunks[i].text
        assert r.dense_vector is None
        assert r.sparse_vector is not None
        assert isinstance(r.sparse_vector, dict)
        for k, v in r.sparse_vector.items():
            assert isinstance(k, str)
            assert isinstance(v, (int, float))
    # c1: hello=2, world=1
    assert records[0].sparse_vector == {"hello": 2.0, "world": 1.0}
    # c2: world=1, foo=1
    assert records[1].sparse_vector == {"world": 1.0, "foo": 1.0}


def test_sparse_encoder_empty_text_explicit_behavior() -> None:
    """空文本对应 sparse_vector 为空 dict，行为明确。"""
    encoder = SparseEncoder()
    chunks = [
        _chunk("", "c1"),
        _chunk("   ", "c2"),
        _chunk("normal", "c3"),
    ]
    records = encoder.encode(chunks, trace=None)
    assert len(records) == 3
    assert records[0].sparse_vector == {}
    assert records[1].sparse_vector == {}
    assert records[2].sparse_vector == {"normal": 1.0}


def test_sparse_encoder_empty_input() -> None:
    """空 chunks 返回空列表。"""
    encoder = SparseEncoder()
    assert encoder.encode([], trace=None) == []


def test_sparse_encoder_preserves_metadata() -> None:
    """ChunkRecord 保留 Chunk 的 metadata。"""
    encoder = SparseEncoder()
    chunks = [Chunk(id="c1", text="x", metadata={"source_path": "a.pdf", "page": 1})]
    records = encoder.encode(chunks, trace=None)
    assert len(records) == 1
    assert records[0].metadata == {"source_path": "a.pdf", "page": 1}


def test_tokenize_lowercase_and_alnum() -> None:
    """分词：仅保留字母数字、小写。"""
    assert _tokenize("Hello World") == ["hello", "world"]
    assert _tokenize("a1b2") == ["a1b2"]
    assert _tokenize("  ") == []


def test_term_frequencies() -> None:
    """词频统计。"""
    assert _term_frequencies([]) == {}
    assert _term_frequencies(["a", "b", "a"]) == {"a": 2.0, "b": 1.0}

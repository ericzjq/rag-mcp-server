"""
VectorUpserter 单元测试（C12）：同一 chunk 两次 upsert 相同 id；内容变更 id 变更；批量顺序保持。
"""

from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from core.types import ChunkRecord
from ingestion.storage.vector_upserter import VectorUpserter, compute_stable_id
from libs.vector_store.base_vector_store import BaseVectorStore


def _record(
    chunk_id: str,
    text: str,
    dense_vector: List[float],
    metadata: Optional[dict] = None,
) -> ChunkRecord:
    return ChunkRecord(
        id=chunk_id,
        text=text,
        metadata=metadata or {},
        dense_vector=dense_vector,
        sparse_vector=None,
    )


class _MockVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        self.upserted: List[List[dict]] = []

    def upsert(
        self,
        records: List[Any],
        trace: Optional[Any] = None,
    ) -> None:
        self.upserted.append([dict(r) for r in records])

    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[dict] = None,
        trace: Optional[Any] = None,
    ) -> List[Any]:
        return []


def test_same_chunk_twice_upsert_same_id() -> None:
    """同一 chunk 两次 upsert 产生相同 id。"""
    store = _MockVectorStore()
    upserter = VectorUpserter(store)
    rec = _record("c1", "hello world", [0.1, 0.2], {"source_path": "a.pdf", "chunk_index": 0})
    ids1 = upserter.upsert([rec], trace=None)
    ids2 = upserter.upsert([rec], trace=None)
    assert len(ids1) == 1 and len(ids2) == 1
    assert ids1[0] == ids2[0]
    assert ids1[0] == compute_stable_id(rec)


def test_content_change_id_changes() -> None:
    """内容变更时 id 变更。"""
    rec1 = _record("c1", "text A", [0.0], {"source_path": "x", "chunk_index": 0})
    rec2 = _record("c1", "text B", [0.0], {"source_path": "x", "chunk_index": 0})
    id1 = compute_stable_id(rec1)
    id2 = compute_stable_id(rec2)
    assert id1 != id2


def test_batch_upsert_preserves_order() -> None:
    """批量 upsert 且保持顺序。"""
    store = _MockVectorStore()
    upserter = VectorUpserter(store)
    records = [
        _record("a", "first", [1.0], {"source_path": "p", "chunk_index": 0}),
        _record("b", "second", [2.0], {"source_path": "p", "chunk_index": 1}),
        _record("c", "third", [3.0], {"source_path": "p", "chunk_index": 2}),
    ]
    ids = upserter.upsert(records, trace=None)
    assert len(ids) == 3
    assert ids[0] == compute_stable_id(records[0])
    assert ids[1] == compute_stable_id(records[1])
    assert ids[2] == compute_stable_id(records[2])
    assert len(store.upserted) == 1
    assert len(store.upserted[0]) == 3
    assert [r["id"] for r in store.upserted[0]] == ids


def test_empty_records_returns_empty_ids() -> None:
    """空 records 返回空 id 列表。"""
    store = _MockVectorStore()
    upserter = VectorUpserter(store)
    assert upserter.upsert([], trace=None) == []
    assert store.upserted == []


def test_stable_id_deterministic_from_metadata_and_text() -> None:
    """compute_stable_id 仅依赖 source_path、chunk_index、text，与 record.id 无关。"""
    r1 = ChunkRecord(id="any", text="same text", metadata={"source_path": "f", "chunk_index": 1}, dense_vector=[0])
    r2 = ChunkRecord(id="other", text="same text", metadata={"source_path": "f", "chunk_index": 1}, dense_vector=[1])
    assert compute_stable_id(r1) == compute_stable_id(r2)

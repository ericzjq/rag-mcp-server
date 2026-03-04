"""
BM25Indexer 单元测试（C11）：build 后 load、同一语料查询返回稳定 top ids；IDF 计算准确；支持重建。
"""

import tempfile
from pathlib import Path

import pytest

from core.types import ChunkRecord
from ingestion.storage.bm25_indexer import BM25Indexer, _idf


def _record(chunk_id: str, text: str, sparse: dict) -> ChunkRecord:
    return ChunkRecord(id=chunk_id, text=text, metadata={}, dense_vector=None, sparse_vector=sparse)


def test_build_save_load_then_query_stable_top_ids() -> None:
    """build 后 save，再 load，对同一语料 query 返回稳定 top ids。"""
    records = [
        _record("c1", "a b c", {"a": 1.0, "b": 1.0, "c": 1.0}),
        _record("c2", "a a b", {"a": 2.0, "b": 1.0}),
        _record("c3", "c c c", {"c": 3.0}),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bm25" / "index.json"
        indexer = BM25Indexer(index_dir=str(path.parent))
        indexer.build(records).save(str(path))
        loaded = BM25Indexer(index_dir=str(path.parent))
        loaded.load(str(path))
        # 查询 "a"：c2 有两个 a，c1 有一个
        top = loaded.query(["a"], top_k=5)
        assert len(top) <= 5
        assert "c2" in top and "c1" in top
        # 多次查询结果一致（稳定）
        top2 = loaded.query(["a"], top_k=5)
        assert top == top2


def test_idf_calculation_known_corpus() -> None:
    """IDF 计算准确：已知 N=3，df(a)=2，df(c)=2，df(b)=1。"""
    n = 3
    assert _idf(n, 0) == 0.0
    # df=1: log((3-1+0.5)/(1+0.5)) = log(2.5/1.5)
    idf_b = _idf(n, 1)
    assert idf_b > 0
    import math
    assert abs(idf_b - math.log((n - 1 + 0.5) / (1 + 0.5))) < 1e-9
    # df=2: log((3-2+0.5)/(2+0.5)) = log(1.5/2.5)
    idf_a = _idf(n, 2)
    assert idf_a < idf_b


def test_build_empty_records() -> None:
    """空 records build 后 query 返回空。"""
    indexer = BM25Indexer()
    indexer.build([])
    assert indexer.query(["any"], top_k=5) == []


def test_save_load_roundtrip() -> None:
    """save 后 load 到新实例，N、avgdl、query 结果一致。"""
    records = [
        _record("x", "hello world", {"hello": 1.0, "world": 1.0}),
        _record("y", "world world", {"world": 2.0}),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "index.json"
        BM25Indexer().build(records).save(str(path))
        other = BM25Indexer().load(str(path))
        top = other.query(["world"], top_k=2)
        assert "y" in top and "x" in top


def test_index_rebuild_overwrite() -> None:
    """支持索引重建：同一 path 再次 build + save 覆盖。"""
    r1 = [_record("c1", "a", {"a": 1.0})]
    r2 = [_record("c1", "b", {"b": 1.0}), _record("c2", "b", {"b": 1.0})]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "idx.json"
        idx = BM25Indexer()
        idx.build(r1).save(str(path))
        top1 = idx.query(["a"], top_k=5)
        assert top1 == ["c1"]
        idx.build(r2).save(str(path))
        idx.load(str(path))
        top2 = idx.query(["b"], top_k=5)
        assert set(top2) == {"c1", "c2"}


def test_merge_into_existing_index() -> None:
    """C16: merge 将新 records 合并进已有索引，N/avgdl/IDF 正确。"""
    r1 = [_record("c1", "a b", {"a": 1.0, "b": 1.0})]
    r2 = [_record("c2", "a c", {"a": 1.0, "c": 1.0})]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "idx.json"
        idx = BM25Indexer()
        idx.build(r1).save(str(path))
        idx.load(str(path))
        idx.merge(r2)
        assert idx._n == 2
        top_a = idx.query(["a"], top_k=5)
        assert set(top_a) == {"c1", "c2"}
        top_c = idx.query(["c"], top_k=5)
        assert top_c == ["c2"]
        idx.save(str(path))
        other = BM25Indexer().load(str(path))
        assert other._n == 2
        assert set(other.query(["a"], top_k=5)) == {"c1", "c2"}


def test_remove_document_does_not_save() -> None:
    """C16: remove_document 只更新内存，不写盘；调用方 save 后持久化。"""
    records = [
        _record("c1", "a b", {"a": 1.0, "b": 1.0}),
        _record("c2", "a c", {"a": 1.0, "c": 1.0}),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "idx.json"
        idx = BM25Indexer()
        idx.build(records).save(str(path))
        idx.load(str(path))
        removed = idx.remove_document(["c1"])
        assert removed == 1
        assert idx._n == 1
        assert idx.query(["a"], top_k=5) == ["c2"]
        # 未 save，磁盘上仍是 2 条
        on_disk = BM25Indexer().load(str(path))
        assert on_disk._n == 2
        idx.save(str(path))
        on_disk2 = BM25Indexer().load(str(path))
        assert on_disk2._n == 1
        assert on_disk2.query(["a"], top_k=5) == ["c2"]

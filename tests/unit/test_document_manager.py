"""
DocumentManager 单元测试（G2）：list_documents、get_document_detail、delete_document、get_collection_stats。
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.document_manager import (
    DocumentManager,
    DocumentInfo,
    DocumentDetail,
    DeleteResult,
    CollectionStats,
    _doc_id_from_path,
)


def test_doc_id_from_path_stable() -> None:
    """_doc_id_from_path 与 PdfLoader 一致，相同路径得到相同 16 位 hash。"""
    p = "/some/path/doc.pdf"
    a = _doc_id_from_path(p)
    b = _doc_id_from_path(p)
    assert a == b
    assert len(a) == 16
    assert all(c in "0123456789abcdef" for c in a)


def test_list_documents_empty_when_integrity_has_no_list_processed() -> None:
    """当 integrity 无 list_processed 时 list_documents 返回空列表。"""
    integrity = MagicMock(spec=["compute_sha256"])
    del integrity.list_processed
    chroma = MagicMock()
    bm25 = MagicMock()
    images = MagicMock()
    mgr = DocumentManager(chroma, bm25, images, integrity)
    assert mgr.list_documents() == []


def test_list_documents_returns_document_info() -> None:
    """list_documents 根据 list_processed 与 chroma/images 返回 DocumentInfo。"""
    integrity = MagicMock()
    integrity.list_processed.return_value = [("/path/to/a.pdf", "hash_a")]
    chroma = MagicMock()
    chroma.get_ids_by_metadata.return_value = ["c1", "c2"]
    images = MagicMock()
    images.list_by_doc_hash.return_value = [{"image_id": "img1"}]
    bm25 = MagicMock()
    mgr = DocumentManager(chroma, bm25, images, integrity)
    docs = mgr.list_documents()
    assert len(docs) == 1
    assert isinstance(docs[0], DocumentInfo)
    assert docs[0].source_path == "/path/to/a.pdf"
    assert docs[0].chunk_count == 2
    assert docs[0].image_count == 1
    chroma.get_ids_by_metadata.assert_called_once_with({"source_path": "/path/to/a.pdf"})
    assert images.list_by_doc_hash.called


def test_get_document_detail_returns_none_for_unknown_doc_id() -> None:
    """未知 doc_id 时 get_document_detail 返回 None。"""
    integrity = MagicMock()
    integrity.list_processed.return_value = []
    chroma = MagicMock()
    bm25 = MagicMock()
    images = MagicMock()
    mgr = DocumentManager(chroma, bm25, images, integrity)
    assert mgr.get_document_detail("unknown_id") is None


def test_get_document_detail_returns_detail_when_found() -> None:
    """找到对应 source_path 时返回 DocumentDetail（chunks + images）。"""
    doc_id = _doc_id_from_path("/f/doc.pdf")
    integrity = MagicMock()
    integrity.list_processed.return_value = [("/f/doc.pdf", "filehash")]
    chroma = MagicMock()
    chroma.get_ids_by_metadata.return_value = ["chunk-1"]
    chroma.get_by_ids.return_value = [
        {"id": "chunk-1", "text": "hello", "metadata": {"source_path": "/f/doc.pdf"}},
    ]
    images = MagicMock()
    images.list_by_doc_hash.return_value = [{"image_id": "i1", "file_path": "/img.png"}]
    bm25 = MagicMock()
    mgr = DocumentManager(chroma, bm25, images, integrity)
    detail = mgr.get_document_detail(doc_id)
    assert detail is not None
    assert isinstance(detail, DocumentDetail)
    assert detail.source_path == "/f/doc.pdf"
    assert detail.doc_id == doc_id
    assert len(detail.chunks) == 1
    assert detail.chunks[0]["text"] == "hello"
    assert len(detail.images) == 1
    assert detail.images[0]["image_id"] == "i1"


def test_delete_document_coordinates_four_stores() -> None:
    """delete_document 协调 chroma、bm25、images、integrity 四个存储。"""
    source_path = "/data/file.pdf"
    doc_id = _doc_id_from_path(source_path)
    chunk_ids = ["chunk-1", "chunk-2"]
    chroma = MagicMock()
    chroma.get_ids_by_metadata.return_value = chunk_ids
    chroma.delete_by_metadata.return_value = 2
    bm25 = MagicMock()
    bm25.load = MagicMock()
    bm25.remove_document.return_value = 2
    images = MagicMock()
    images.delete_by_doc_hash.return_value = 1
    integrity = MagicMock()
    integrity.compute_sha256.return_value = "abc" + "0" * 61
    integrity.remove_record.return_value = True
    mgr = DocumentManager(chroma, bm25, images, integrity)
    result = mgr.delete_document(source_path)
    assert isinstance(result, DeleteResult)
    assert result.source_path == source_path
    assert result.chroma_deleted == 2
    assert result.bm25_removed == 2
    assert result.images_deleted == 1
    assert result.integrity_removed is True
    chroma.delete_by_metadata.assert_called_once_with({"source_path": source_path})
    bm25.remove_document.assert_called_once_with(chunk_ids)
    images.delete_by_doc_hash.assert_called_once_with(doc_id)
    integrity.remove_record.assert_called_once()


def test_get_collection_stats_aggregates_list_documents() -> None:
    """get_collection_stats 基于 list_documents 聚合文档数、chunk 数、图片数。"""
    integrity = MagicMock()
    integrity.list_processed.return_value = [
        ("/a.pdf", "h1"),
        ("/b.pdf", "h2"),
    ]
    chroma = MagicMock()
    chroma.get_ids_by_metadata.side_effect = [["c1", "c2"], ["c3"]]
    images = MagicMock()
    images.list_by_doc_hash.side_effect = [[], [{"image_id": "i1"}]]
    bm25 = MagicMock()
    mgr = DocumentManager(chroma, bm25, images, integrity)
    stats = mgr.get_collection_stats()
    assert isinstance(stats, CollectionStats)
    assert stats.document_count == 2
    assert stats.chunk_count == 3
    assert stats.image_count == 1


def test_delete_after_list_removes_from_list(tmp_path: Path) -> None:
    """删除后再次 list_documents 不包含已删除文档（集成式：真实 SQLiteIntegrity + Chroma + BM25 + Image）。"""
    from libs.loader.file_integrity import SQLiteIntegrityChecker
    from libs.vector_store.chroma_store import ChromaStore
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

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    persist = str(tmp_path / "chroma")
    Path(persist).mkdir(parents=True)
    bm25_dir = str(tmp_path / "bm25")
    Path(bm25_dir).mkdir(parents=True)
    img_db = str(db_dir / "image_index.db")
    img_base = str(tmp_path / "images")
    Path(img_base).mkdir(parents=True)
    integrity_db = str(db_dir / "ingestion.db")

    settings = Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory=persist),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )
    chroma = ChromaStore(settings)
    integrity = SQLiteIntegrityChecker(db_path=integrity_db)
    from ingestion.storage.bm25_indexer import BM25Indexer
    from ingestion.storage.image_storage import ImageStorage
    from core.types import ChunkRecord

    # 模拟一条已摄入文档：integrity success + chroma 2 chunks + image 1
    source_path = str(tmp_path / "doc.pdf")
    Path(source_path).write_bytes(b"fake pdf")
    file_hash = integrity.compute_sha256(source_path)
    integrity.mark_success(file_hash, source_path)
    doc_id = _doc_id_from_path(source_path)
    records = [
        {"id": "chunk-1", "vector": [0.1] * 8, "metadata": {"source_path": source_path, "text": "t1"}},
        {"id": "chunk-2", "vector": [0.2] * 8, "metadata": {"source_path": source_path, "text": "t2"}},
    ]
    chroma.upsert(records, trace=None)
    indexer = BM25Indexer(index_dir=bm25_dir)
    cr1 = ChunkRecord(id="chunk-1", text="t1", metadata={"source_path": source_path}, sparse_vector={"a": 1.0})
    cr2 = ChunkRecord(id="chunk-2", text="t2", metadata={"source_path": source_path}, sparse_vector={"b": 1.0})
    indexer.build([cr1, cr2]).save()
    img_storage = ImageStorage(db_path=img_db, images_base=img_base)
    img_storage.register("img1.png", img_base + "/_default/img1.png", collection="default", doc_hash=doc_id)

    mgr = DocumentManager(chroma, indexer, img_storage, integrity)
    docs_before = mgr.list_documents()
    assert len(docs_before) == 1
    assert docs_before[0].source_path == source_path
    assert docs_before[0].chunk_count == 2
    assert docs_before[0].image_count == 1

    result = mgr.delete_document(source_path)
    assert result.chroma_deleted == 2
    assert result.integrity_removed is True

    docs_after = mgr.list_documents()
    assert len(docs_after) == 0

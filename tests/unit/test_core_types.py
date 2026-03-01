"""
核心数据类型单元测试（C1）：Document / Chunk / ChunkRecord 序列化、metadata 约定、images 规范。
"""

import json

import pytest

from core.types import Chunk, ChunkRecord, Document


def test_document_to_dict_and_from_dict_roundtrip() -> None:
    """Document 可序列化为 dict 并反序列化，字段稳定。"""
    meta = {"source_path": "/path/to/doc.pdf"}
    doc = Document(id="doc1", text="Hello world", metadata=meta)
    d = doc.to_dict()
    assert d["id"] == "doc1"
    assert d["text"] == "Hello world"
    assert d["metadata"]["source_path"] == "/path/to/doc.pdf"
    doc2 = Document.from_dict(d)
    assert doc2.id == doc.id and doc2.text == doc.text and doc2.metadata == doc.metadata


def test_document_metadata_at_least_source_path_convention() -> None:
    """metadata 约定最少包含 source_path，单元测试断言。"""
    doc = Document(id="d1", text="x", metadata={"source_path": "a.pdf"})
    assert doc.metadata.get("source_path") == "a.pdf"
    doc_extra = Document(id="d2", text="y", metadata={"source_path": "b.pdf", "page_count": 3})
    assert doc_extra.metadata["source_path"] == "b.pdf"
    assert doc_extra.metadata["page_count"] == 3


def test_document_metadata_images_spec_structure() -> None:
    """metadata.images 为 List[dict]，含 id/path/page/text_offset/text_length/position。"""
    images = [
        {
            "id": "doc_hash_1_0",
            "path": "data/images/col1/doc_hash_1_0.png",
            "page": 1,
            "text_offset": 10,
            "text_length": 24,
            "position": {"x": 0, "y": 0},
        }
    ]
    doc = Document(id="d1", text="before [IMAGE: doc_hash_1_0] after", metadata={"source_path": "x.pdf", "images": images})
    assert len(doc.metadata["images"]) == 1
    img = doc.metadata["images"][0]
    assert img["id"] == "doc_hash_1_0"
    assert "path" in img and "text_offset" in img and "text_length" in img


def test_document_text_image_placeholder_convention() -> None:
    """Document.text 中图片占位符为 [IMAGE: {image_id}]。"""
    doc = Document(id="d1", text="See [IMAGE: img_001] here", metadata={"source_path": "f"})
    assert "[IMAGE: img_001]" in doc.text


def test_document_serializable_json() -> None:
    """类型可序列化为 JSON。"""
    doc = Document(id="j1", text="t", metadata={"source_path": "p"})
    s = json.dumps(doc.to_dict(), ensure_ascii=False)
    loaded = json.loads(s)
    assert Document.from_dict(loaded).id == doc.id


def test_chunk_to_dict_and_from_dict_roundtrip() -> None:
    """Chunk 可序列化为 dict 并反序列化。"""
    c = Chunk(id="ch1", text="chunk text", metadata={"source_path": "a"}, start_offset=0, end_offset=10, source_ref="doc1")
    d = c.to_dict()
    assert d["id"] == "ch1" and d["start_offset"] == 0 and d["end_offset"] == 10 and d.get("source_ref") == "doc1"
    c2 = Chunk.from_dict(d)
    assert c2.id == c.id and c2.start_offset == c.start_offset and c2.source_ref == c.source_ref


def test_chunk_without_source_ref_optional() -> None:
    """Chunk.source_ref 可选。"""
    c = Chunk(id="ch2", text="t", metadata={}, start_offset=0, end_offset=5)
    d = c.to_dict()
    assert "source_ref" not in d or d.get("source_ref") is None
    c2 = Chunk.from_dict(d)
    assert c2.source_ref is None


def test_chunk_record_with_vectors() -> None:
    """ChunkRecord 含可选 dense_vector、sparse_vector。"""
    r = ChunkRecord(id="r1", text="t", metadata={"source_path": "x"}, dense_vector=[0.1, 0.2], sparse_vector={"0": 0.5})
    d = r.to_dict()
    assert d["dense_vector"] == [0.1, 0.2]
    assert d["sparse_vector"] == {"0": 0.5}
    r2 = ChunkRecord.from_dict(d)
    assert r2.dense_vector == r.dense_vector and r2.sparse_vector == r.sparse_vector


def test_chunk_record_without_vectors() -> None:
    """ChunkRecord 可无向量字段。"""
    r = ChunkRecord(id="r2", text="t", metadata={"source_path": "y"})
    d = r.to_dict()
    assert "dense_vector" not in d and "sparse_vector" not in d
    r2 = ChunkRecord.from_dict(d)
    assert r2.dense_vector is None and r2.sparse_vector is None


def test_chunk_record_json_roundtrip() -> None:
    """ChunkRecord 可 JSON 序列化并反序列化。"""
    r = ChunkRecord(id="r3", text="t", metadata={}, dense_vector=[0.0])
    s = json.dumps(r.to_dict())
    loaded = json.loads(s)
    r2 = ChunkRecord.from_dict(loaded)
    assert r2.id == r.id and r2.dense_vector == r.dense_vector

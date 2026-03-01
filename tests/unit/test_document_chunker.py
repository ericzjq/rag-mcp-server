"""
DocumentChunker 单元测试（C4）：FakeSplitter 隔离，ID 唯一/确定、metadata、source_ref、契约。
"""

from typing import Any, List, Optional

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
from core.types import Chunk, Document
from ingestion.chunking.document_chunker import (
    DocumentChunker,
    _generate_chunk_id,
    _inherit_metadata,
)
from libs.splitter.base_splitter import BaseSplitter
from libs.splitter.splitter_factory import create as create_splitter, register_splitter_provider


def _make_settings(
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    splitter_provider: str = "fake",
) -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(
            provider=splitter_provider,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class FakeSplitter(BaseSplitter):
    """按空格切分，便于断言。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def split_text(self, text: str, trace: Optional[Any] = None) -> List[str]:
        return [s for s in text.split() if s] if text.strip() else []


def test_split_document_returns_chunks_with_source_ref_and_metadata() -> None:
    """split_document 产出 Chunk，source_ref 指向 Document.id，metadata 含 Document.metadata + chunk_index。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        settings = _make_settings(splitter_provider="fake")
        chunker = DocumentChunker(settings)
        doc = Document(id="doc1", text="a b c", metadata={"source_path": "/x.pdf"})
        chunks = chunker.split_document(doc, trace=None)
        assert len(chunks) == 3
        for i, c in enumerate(chunks):
            assert c.source_ref == "doc1"
            assert c.metadata.get("source_path") == "/x.pdf"
            assert c.metadata.get("chunk_index") == i
    finally:
        from libs.splitter import splitter_factory
        splitter_factory._PROVIDERS.pop("fake", None)


def test_chunk_id_unique_and_deterministic() -> None:
    """同一文档内 Chunk ID 唯一；同一 Document 重复切分得到相同 ID 序列。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        settings = _make_settings(splitter_provider="fake")
        chunker = DocumentChunker(settings)
        doc = Document(id="d1", text="x y z", metadata={})
        c1 = chunker.split_document(doc, trace=None)
        c2 = chunker.split_document(doc, trace=None)
        ids1 = [c.id for c in c1]
        ids2 = [c.id for c in c2]
        assert ids1 == ids2
        assert len(ids1) == len(set(ids1))
    finally:
        from libs.splitter import splitter_factory
        splitter_factory._PROVIDERS.pop("fake", None)


def test_generate_chunk_id_format() -> None:
    """_generate_chunk_id 格式为 {doc_id}_{index:04d}_{hash_8chars}。"""
    cid = _generate_chunk_id("doc1", 0, "hello")
    assert cid.startswith("doc1_0000_")
    assert len(cid) == len("doc1_0000_") + 8
    assert cid.split("_")[0] == "doc1" and cid.split("_")[1] == "0000"


def test_inherit_metadata_includes_chunk_index() -> None:
    """_inherit_metadata 复制 Document.metadata 并添加 chunk_index。"""
    doc = Document(id="d", text="t", metadata={"source_path": "/a", "title": "T"})
    meta = _inherit_metadata(doc, 2)
    assert meta["source_path"] == "/a" and meta["title"] == "T" and meta["chunk_index"] == 2


def test_empty_document_returns_empty_list() -> None:
    """空文本 Document 返回空列表。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        settings = _make_settings(splitter_provider="fake")
        chunker = DocumentChunker(settings)
        doc = Document(id="e", text="   \n\n  ", metadata={})
        assert chunker.split_document(doc, trace=None) == []
    finally:
        from libs.splitter import splitter_factory
        splitter_factory._PROVIDERS.pop("fake", None)


def test_chunks_are_serializable_and_conform_to_core_types() -> None:
    """输出的 Chunk 可 to_dict 且字段符合 core.types.Chunk。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        settings = _make_settings(splitter_provider="fake")
        chunker = DocumentChunker(settings)
        doc = Document(id="s", text="one two", metadata={"source_path": "f"})
        chunks = chunker.split_document(doc, trace=None)
        for c in chunks:
            d = c.to_dict()
            assert "id" in d and "text" in d and "metadata" in d and "start_offset" in d and "end_offset" in d
            assert "source_ref" in d and d["source_ref"] == "s"
            c2 = Chunk.from_dict(d)
            assert c2.id == c.id and c2.text == c.text
    finally:
        from libs.splitter import splitter_factory
        splitter_factory._PROVIDERS.pop("fake", None)


def test_config_driven_chunk_count() -> None:
    """不同 splitter 配置（Fake 按空格）导致不同 chunk 数量。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        doc = Document(id="cfg", text="a b c d e", metadata={})
        settings = _make_settings(splitter_provider="fake")
        chunker = DocumentChunker(settings)
        chunks = chunker.split_document(doc, trace=None)
        assert len(chunks) == 5
    finally:
        from libs.splitter import splitter_factory
        splitter_factory._PROVIDERS.pop("fake", None)

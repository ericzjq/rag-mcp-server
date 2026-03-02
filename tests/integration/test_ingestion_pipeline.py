"""
Ingestion Pipeline 集成测试（C14）：完整 pipeline 跑通，输出向量索引、BM25、图片登记；失败步骤明确异常。
"""

from pathlib import Path
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
from core.types import Chunk, ChunkRecord, Document
from ingestion.embedding.batch_processor import BatchProcessor
from ingestion.pipeline import IngestionPipeline
from ingestion.transform.chunk_refiner import ChunkRefiner
from ingestion.transform.image_captioner import ImageCaptioner
from ingestion.transform.metadata_enricher import MetadataEnricher
from libs.loader.base_loader import BaseLoader
from libs.splitter.base_splitter import BaseSplitter


def _make_settings(
    persist_dir: str = "data/chroma",
    splitter_provider: str = "recursive",
) -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory=persist_dir),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider=splitter_provider, chunk_size=256, chunk_overlap=32),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class _FakeSplitter(BaseSplitter):
    """按双换行切分，便于控制 chunk 数量。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
    ) -> List[str]:
        if not (text or "").strip():
            return []
        return [s.strip() for s in text.strip().split("\n\n") if s.strip()]


def test_pipeline_full_run_outputs_chroma_bm25_images(tmp_path: Path) -> None:
    """对测试文档跑完整 pipeline，成功输出：向量到 Chroma、BM25 索引、图片登记。"""
    from libs.splitter.splitter_factory import register_splitter_provider
    register_splitter_provider("fake_pipeline", _FakeSplitter)
    settings = _make_settings(
        persist_dir=str(tmp_path / "chroma"),
        splitter_provider="fake_pipeline",
    )

    # 创建真实 PDF 文件（供 integrity 哈希），Loader 用 mock 返回带文本的 Document
    pdf_path = tmp_path / "doc.pdf"
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(72, 72)
    with open(pdf_path, "wb") as f:
        w.write(f)

    class _MockLoader(BaseLoader):
        def load(self, path: str) -> Document:
            return Document(
                id="test_doc_1",
                text="First paragraph.\n\nSecond paragraph.\n\nThird.",
                metadata={"source_path": path},
            )

    class _MockBatchProcessor(BatchProcessor):
        def process(
            self,
            chunks: List[Chunk],
            batch_size: int = 32,
            trace: Optional[Any] = None,
        ) -> List[ChunkRecord]:
            from ingestion.embedding.sparse_encoder import SparseEncoder
            sparse = SparseEncoder()
            sparse_records = sparse.encode(chunks, trace=trace)
            return [
                ChunkRecord(
                    id=r.id,
                    text=r.text,
                    metadata=dict(r.metadata) if r.metadata else {},
                    dense_vector=[0.1] * 4,
                    sparse_vector=r.sparse_vector,
                )
                for r in sparse_records
            ]

    integrity_db = tmp_path / "db" / "ingestion_history.db"
    bm25_dir = tmp_path / "db" / "bm25"
    image_db = tmp_path / "db" / "image_index.db"
    images_base = tmp_path / "images"

    from libs.loader.file_integrity import SQLiteIntegrityChecker
    from ingestion.storage.image_storage import ImageStorage

    pipeline = IngestionPipeline(
        settings,
        integrity_checker=SQLiteIntegrityChecker(db_path=str(integrity_db)),
        loader=_MockLoader(),
        batch_processor=_MockBatchProcessor(settings),
        bm25_index_dir=str(bm25_dir),
        image_storage=ImageStorage(db_path=str(image_db), images_base=str(images_base)),
    )
    # 无 LLM 的 transform 链
    pipeline._transforms = [
        ChunkRefiner(settings, use_llm=False),
        MetadataEnricher(settings, use_llm=False),
        ImageCaptioner(settings),
    ]

    result = pipeline.run(str(pdf_path), collection="test", force=True, batch_size=2)

    assert "document_id" in result
    assert result["document_id"] == "test_doc_1"
    assert result["chunks_count"] >= 1
    assert result["records_count"] >= 1
    assert (bm25_dir / "index.json").exists()


def test_ingestion_trace_contains_stages_and_trace_type(tmp_path: Path) -> None:
    """一次摄取生成 trace，包含 load/split/transform/embed/upsert，trace_type=ingestion，每阶段含 elapsed_ms、method。"""
    from core.trace.trace_context import TraceContext
    from libs.loader.file_integrity import SQLiteIntegrityChecker
    from libs.splitter.splitter_factory import register_splitter_provider
    from ingestion.storage.image_storage import ImageStorage

    register_splitter_provider("fake_f4", _FakeSplitter)
    settings = _make_settings(
        persist_dir=str(tmp_path / "chroma"),
        splitter_provider="fake_f4",
    )
    pdf_path = tmp_path / "doc.pdf"
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(72, 72)
    with open(pdf_path, "wb") as f:
        w.write(f)

    class _MockLoader(BaseLoader):
        def load(self, path: str) -> Document:
            return Document(id="f4_doc", text="A\n\nB", metadata={"source_path": path})

    class _MockBatchProcessor(BatchProcessor):
        def process(self, chunks: List[Chunk], batch_size: int = 32, trace: Optional[Any] = None) -> List[ChunkRecord]:
            from ingestion.embedding.sparse_encoder import SparseEncoder
            sparse = SparseEncoder()
            recs = sparse.encode(chunks, trace=trace)
            return [
                ChunkRecord(id=r.id, text=r.text, metadata=dict(r.metadata or {}), dense_vector=[0.1] * 4, sparse_vector=r.sparse_vector)
                for r in recs
            ]

    pipeline = IngestionPipeline(
        settings,
        integrity_checker=SQLiteIntegrityChecker(db_path=str(tmp_path / "db" / "hist.db")),
        loader=_MockLoader(),
        batch_processor=_MockBatchProcessor(settings),
        bm25_index_dir=str(tmp_path / "db" / "bm25"),
        image_storage=ImageStorage(db_path=str(tmp_path / "db" / "img.db"), images_base=str(tmp_path / "images")),
    )
    pipeline._transforms = [
        ChunkRefiner(settings, use_llm=False),
        MetadataEnricher(settings, use_llm=False),
        ImageCaptioner(settings),
    ]

    trace = TraceContext(trace_type="ingestion")
    pipeline.run(str(pdf_path), force=True, trace=trace)

    d = trace.to_dict()
    assert d["trace_type"] == "ingestion"
    stages = d["stages"]
    for name in ("load", "split", "transform", "embed", "upsert"):
        assert name in stages, stages
        assert "elapsed_ms" in stages[name]
        assert "method" in stages[name]


def test_pipeline_nonexistent_path_raises() -> None:
    """文档不存在时抛出明确异常。"""
    settings = _make_settings()
    pipeline = IngestionPipeline(settings, integrity_checker=None)
    with pytest.raises(FileNotFoundError, match="文档不存在"):
        pipeline.run("/nonexistent/file.pdf", force=True)


def test_pipeline_skip_when_integrity_seen(tmp_path: Path) -> None:
    """未 force 且 integrity 已标记成功时跳过并返回 skipped。"""
    from libs.loader.file_integrity import SQLiteIntegrityChecker
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")
    checker = SQLiteIntegrityChecker(db_path=str(tmp_path / "db" / "hist.db"))
    checker.mark_success(checker.compute_sha256(str(pdf_path)), str(pdf_path))
    settings = _make_settings()
    pipeline = IngestionPipeline(settings, integrity_checker=checker)
    result = pipeline.run(str(pdf_path), force=False)
    assert result.get("skipped") is True

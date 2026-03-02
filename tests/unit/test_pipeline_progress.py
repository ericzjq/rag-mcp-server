"""
Pipeline 进度回调单元测试（F5）：on_progress 各阶段被调用且参数正确。
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
from ingestion.transform.metadata_enricher import MetadataEnricher
from ingestion.transform.image_captioner import ImageCaptioner
from libs.loader.base_loader import BaseLoader
from libs.splitter.base_splitter import BaseSplitter


def _make_settings(splitter_provider: str = "recursive") -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider=splitter_provider, chunk_size=256, chunk_overlap=32),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class _FakeSplitter(BaseSplitter):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def split_text(self, text: str, trace: Optional[Any] = None) -> List[str]:
        if not (text or "").strip():
            return []
        return [s.strip() for s in text.strip().split("\n\n") if s.strip()]


def test_on_progress_called_for_each_stage(tmp_path: Path) -> None:
    """传入 on_progress 时，load/split/transform/embed/upsert 各阶段均被调用且参数正确。"""
    from libs.splitter.splitter_factory import register_splitter_provider
    register_splitter_provider("fake_progress", _FakeSplitter)

    settings = _make_settings(splitter_provider="fake_progress")
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    class _MockLoader(BaseLoader):
        def load(self, path: str) -> Document:
            return Document(id="p1", text="A\n\nB\n\nC", metadata={"source_path": path})

    class _MockBatchProcessor(BatchProcessor):
        def process(self, chunks: List[Chunk], batch_size: int = 32, trace: Optional[Any] = None) -> List[ChunkRecord]:
            from ingestion.embedding.sparse_encoder import SparseEncoder
            enc = SparseEncoder()
            recs = enc.encode(chunks, trace=trace)
            return [
                ChunkRecord(id=r.id, text=r.text, metadata=dict(r.metadata or {}), dense_vector=[0.1] * 4, sparse_vector=r.sparse_vector)
                for r in recs
            ]

    pipeline = IngestionPipeline(
        settings,
        integrity_checker=None,
        loader=_MockLoader(),
        batch_processor=_MockBatchProcessor(settings),
        bm25_index_dir=str(tmp_path / "bm25"),
        vector_store=MagicMock(),
    )
    pipeline._transforms = [
        ChunkRefiner(settings, use_llm=False),
        MetadataEnricher(settings, use_llm=False),
        ImageCaptioner(settings),
    ]

    progress_calls: List[tuple] = []

    def on_progress(stage_name: str, current: int, total: int) -> None:
        progress_calls.append((stage_name, current, total))

    pipeline.run(str(pdf_path), force=True, on_progress=on_progress)

    assert len(progress_calls) >= 5
    stages_seen = {s[0] for s in progress_calls}
    assert "load" in stages_seen
    assert "split" in stages_seen
    assert "transform" in stages_seen
    assert "embed" in stages_seen
    assert "upsert" in stages_seen
    for (name, cur, tot) in progress_calls:
        assert isinstance(name, str)
        assert isinstance(cur, int) and cur >= 0
        assert isinstance(tot, int) and tot >= 0
    load_call = next(c for c in progress_calls if c[0] == "load")
    assert load_call == ("load", 1, 1)
    split_call = next(c for c in progress_calls if c[0] == "split")
    assert split_call[1] == split_call[2]  # current == total (chunks count)
    assert split_call[1] >= 1


def test_on_progress_none_no_effect() -> None:
    """on_progress 为 None 时不影响运行，不抛错。"""
    settings = _make_settings()
    pipeline = IngestionPipeline(settings, integrity_checker=None)
    with pytest.raises(FileNotFoundError):
        pipeline.run("/nonexistent.pdf", force=True, on_progress=None)
    with pytest.raises(FileNotFoundError):
        pipeline.run("/nonexistent.pdf", force=True)

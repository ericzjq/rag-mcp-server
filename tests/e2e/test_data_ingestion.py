"""
E2E 测试（C15）：脚本入口可运行，data/db 产生产物；重复运行在未变更时跳过。
使用临时目录，mock 编码层避免真实 API 调用。
"""

import subprocess
import sys
from pathlib import Path

import pytest

# 项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ingest_script_help() -> None:
    """脚本可执行且 --help 正常。"""
    script = PROJECT_ROOT / "scripts" / "ingest.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--path" in result.stdout
    assert "--collection" in result.stdout
    assert "--force" in result.stdout


def test_ingest_produces_data_db_and_skips_on_second_run(tmp_path: Path) -> None:
    """跑一次摄取在 data/db 产生产物；再跑一次（不 --force）跳过。"""
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
    from core.types import ChunkRecord, Document
    from ingestion.embedding.batch_processor import BatchProcessor
    from ingestion.pipeline import IngestionPipeline
    from ingestion.storage.image_storage import ImageStorage
    from libs.loader.base_loader import BaseLoader
    from libs.loader.file_integrity import SQLiteIntegrityChecker

    # 临时目录下创建 config 与 PDF
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    config = tmp_path / "config" / "settings.yaml"
    config.write_text("""
llm: { provider: openai, model: gpt-4o-mini }
embedding: { provider: openai, model: text-embedding-3-small }
vector_store: { provider: chroma, persist_directory: data/chroma }
retrieval: { top_k: 10, rerank_top_m: 20 }
rerank: { provider: none }
splitter: { provider: recursive, chunk_size: 256, chunk_overlap: 32 }
evaluation: { provider: ragas }
observability: { log_level: INFO, traces_path: logs/traces.jsonl }
""", encoding="utf-8")

    pdf_path = tmp_path / "doc.pdf"
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(72, 72)
    with open(pdf_path, "wb") as f:
        w.write(f)

    settings = Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory=str(tmp_path / "data" / "chroma")),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=256, chunk_overlap=32),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path=str(tmp_path / "logs" / "traces.jsonl")),
    )

    class _MockLoader(BaseLoader):
        def load(self, path: str) -> Document:
            return Document(
                id="e2e_doc",
                text="Chunk one.\n\nChunk two.",
                metadata={"source_path": path},
            )

    class _MockBatchProcessor(BatchProcessor):
        def process(self, chunks, batch_size=32, trace=None):
            from ingestion.embedding.sparse_encoder import SparseEncoder
            sparse = SparseEncoder()
            sr = sparse.encode(chunks, trace=trace)
            return [
                ChunkRecord(id=r.id, text=r.text, metadata=dict(r.metadata or {}), dense_vector=[0.1] * 4, sparse_vector=r.sparse_vector)
                for r in sr
            ]

    integrity_db = tmp_path / "data" / "db" / "ingestion_history.db"
    integrity_db.parent.mkdir(parents=True, exist_ok=True)
    bm25_dir = tmp_path / "data" / "db" / "bm25"
    image_db = tmp_path / "data" / "db" / "image_index.db"
    images_base = tmp_path / "data" / "images"

    pipeline = IngestionPipeline(
        settings,
        integrity_checker=SQLiteIntegrityChecker(db_path=str(integrity_db)),
        loader=_MockLoader(),
        batch_processor=_MockBatchProcessor(settings),
        bm25_index_dir=str(bm25_dir),
        image_storage=ImageStorage(db_path=str(image_db), images_base=str(images_base)),
    )

    # 第一次运行：应产生产物，并写入 integrity（以便第二次跳过）
    result1 = pipeline.run(str(pdf_path), collection="e2e", force=False)
    assert "skipped" not in result1 or not result1["skipped"]
    assert result1.get("records_count", 0) >= 1
    assert (bm25_dir / "index.json").exists()
    assert integrity_db.exists()

    # 第二次运行（未变更、不 force）：应跳过
    result2 = pipeline.run(str(pdf_path), collection="e2e", force=False)
    assert result2.get("skipped") is True

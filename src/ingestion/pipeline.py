"""
Pipeline（C14）：串行执行 integrity→load→split→transform→encode→store，失败步骤抛出清晰异常。F4 打点。
"""

import logging
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

from core.settings import Settings
from core.trace.trace_context import TraceContext
from core.types import Chunk, ChunkRecord, Document

from ingestion.chunking.document_chunker import DocumentChunker
from ingestion.embedding.batch_processor import BatchProcessor
from ingestion.storage.bm25_indexer import BM25Indexer
from ingestion.storage.image_storage import ImageStorage
from ingestion.storage.vector_upserter import VectorUpserter
from ingestion.transform.base_transform import BaseTransform
from ingestion.transform.chunk_refiner import ChunkRefiner
from ingestion.transform.image_captioner import ImageCaptioner
from ingestion.transform.metadata_enricher import MetadataEnricher
from libs.loader.base_loader import BaseLoader
from libs.loader.file_integrity import FileIntegrityChecker
from libs.loader.pdf_loader import PdfLoader
from libs.vector_store.base_vector_store import BaseVectorStore
from libs.vector_store.vector_store_factory import create as create_vector_store

logger = logging.getLogger(__name__)

DEFAULT_BM25_INDEX_DIR = "data/db/bm25"
DEFAULT_BATCH_SIZE = 32


class IngestionPipeline:
    """摄取流水线：integrity → load → 登记图片 → split → transform → encode → store。"""

    def __init__(
        self,
        settings: Settings,
        *,
        integrity_checker: Optional[FileIntegrityChecker] = None,
        loader: Optional[BaseLoader] = None,
        chunker: Optional[DocumentChunker] = None,
        transforms: Optional[List[BaseTransform]] = None,
        batch_processor: Optional[BatchProcessor] = None,
        vector_store: Optional[BaseVectorStore] = None,
        bm25_index_dir: str = DEFAULT_BM25_INDEX_DIR,
        image_storage: Optional[ImageStorage] = None,
    ) -> None:
        self._settings = settings
        self._integrity = integrity_checker
        self._loader = loader if loader is not None else PdfLoader(images_base_dir="data/images")
        self._chunker = chunker if chunker is not None else DocumentChunker(settings)
        # 默认 ChunkRefiner use_llm=False，避免大文档时对每个 chunk 调 LLM（225 条即 225 次调用）导致 transform 极慢
        self._transforms = transforms if transforms is not None else [
            ChunkRefiner(settings, use_llm=False),
            MetadataEnricher(settings),
            ImageCaptioner(settings),
        ]
        bp = batch_processor if batch_processor is not None else BatchProcessor(settings)
        self._batch_processor = bp
        vs = vector_store if vector_store is not None else create_vector_store(settings)
        self._vector_upserter = VectorUpserter(vs)
        self._bm25_index_dir = bm25_index_dir
        self._image_storage = image_storage if image_storage is not None else ImageStorage()

    def run(
        self,
        path: str,
        collection: str = "",
        force: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
        trace: Optional[TraceContext] = None,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict:
        """
        对单文件执行完整摄取；失败时抛出明确异常。

        Args:
            path: 文档路径（如 PDF）。
            collection: 可选集合名（用于图片登记）。
            force: 若 True 跳过 integrity 检查强制重新摄取。
            batch_size: 编码批大小。
            trace: 可选追踪上下文。
            on_progress: 可选进度回调 (stage_name, current, total)，各阶段完成时触发。

        Returns:
            摘要 dict：document_id, chunks_count, records_count 等。
        """
        trace = trace or TraceContext(trace_type="ingestion")
        if not path or not Path(path).exists():
            raise FileNotFoundError(f"文档不存在: {path}")

        # 1. Integrity + 计算 file_hash（用于后续按内容去重：同一文件不同 path 只保留最新一次）
        file_hash = None
        if self._integrity is not None:
            file_hash = self._integrity.compute_sha256(path)
            if not force and self._integrity.should_skip(file_hash):
                logger.info("跳过已摄取文件 (hash=%s): %s", file_hash[:8], path)
                return {"skipped": True, "file_hash": file_hash[:16]}

        # 2. Load
        logger.info("加载文档: %s", path)
        t0 = time.perf_counter()
        document = self._loader.load(path)
        if file_hash is not None:
            document = Document(
                id=document.id,
                text=document.text,
                metadata={**document.metadata, "file_hash": file_hash},
            )
        trace.record_stage("load", {
            "document_id": document.id,
            "method": type(self._loader).__name__.lower().replace("loader", "") or "loader",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        })
        if on_progress is not None:
            on_progress("load", 1, 1)

        # 3. 登记图片到 ImageStorage（Loader 已写入文件）
        images = document.metadata.get("images") if document.metadata else []
        if images and self._image_storage:
            coll = collection or document.id
            for img in images:
                if isinstance(img, dict) and img.get("id") and img.get("path"):
                    self._image_storage.register(
                        img["id"],
                        img["path"],
                        collection=coll,
                        doc_hash=document.id,
                        page_num=img.get("page"),
                    )

        # 4. Split
        logger.info("分块: document_id=%s", document.id)
        t1 = time.perf_counter()
        chunks = self._chunker.split_document(document, trace=trace)
        if not chunks:
            logger.warning("文档分块为空: %s", path)
            if on_progress is not None:
                on_progress("split", 0, 0)
            if self._integrity is not None and not force and file_hash is not None:
                self._integrity.mark_success(file_hash, path)
            trace.finish()
            return {"document_id": document.id, "chunks_count": 0, "records_count": 0}
        trace.record_stage("split", {
            "chunks_count": len(chunks),
            "method": getattr(self._settings.splitter, "provider", "splitter"),
            "elapsed_ms": round((time.perf_counter() - t1) * 1000, 2),
        })
        if on_progress is not None:
            on_progress("split", len(chunks), len(chunks))

        # 5. Transform（可能较慢：ChunkRefiner/MetadataEnricher/ImageCaptioner 会调 LLM）
        if on_progress is not None:
            on_progress("transform", 0, len(chunks))
        t2 = time.perf_counter()
        for i, t in enumerate(self._transforms):
            chunks = t.transform(chunks, trace=trace)
        trace.record_stage("transform", {
            "chunks_count": len(chunks),
            "method": ",".join(type(x).__name__.lower() for x in self._transforms),
            "elapsed_ms": round((time.perf_counter() - t2) * 1000, 2),
        })
        if on_progress is not None:
            on_progress("transform", len(chunks), len(chunks))

        # 6. Encode (embed)（可能较慢：调用 embedding API 分批处理）
        if on_progress is not None:
            on_progress("embed", 0, len(chunks))
        logger.info("编码: %d chunks", len(chunks))
        # 部分 embedding 接口单次请求条数有限制（如 Qwen 最多 10 条）
        effective_batch = batch_size
        if getattr(self._settings.embedding, "provider", "") == "qwen":
            effective_batch = min(batch_size, 10)
        t3 = time.perf_counter()
        records = self._batch_processor.process(chunks, batch_size=effective_batch, trace=trace)
        trace.record_stage("embed", {
            "records_count": len(records),
            "method": getattr(self._settings.embedding, "provider", "embedding"),
            "elapsed_ms": round((time.perf_counter() - t3) * 1000, 2),
        })
        if on_progress is not None:
            on_progress("embed", len(records), len(records))

        # 7. Store (upsert)
        logger.info("写入向量与 BM25 索引")
        t4 = time.perf_counter()
        stored_ids, deleted_ids = self._vector_upserter.upsert(records, trace=trace)
        # BM25 必须使用与 Chroma 相同的 chunk_id，否则 Dense/Sparse 融合时同一 chunk 会以两种 id 各出现一次导致重复
        records_for_bm25 = [
            ChunkRecord(id=stored_ids[i], text=r.text, metadata=r.metadata, dense_vector=r.dense_vector, sparse_vector=r.sparse_vector)
            for i, r in enumerate(records)
        ]
        indexer = BM25Indexer(index_dir=self._bm25_index_dir)
        try:
            indexer.load()
        except (FileNotFoundError, OSError):
            pass  # 无已有索引则视为空，merge 后即当前文档
        indexer.remove_document(deleted_ids)
        indexer.merge(records_for_bm25)
        indexer.save()
        trace.record_stage("upsert", {
            "method": getattr(self._settings.vector_store, "provider", "chroma") + ",bm25",
            "elapsed_ms": round((time.perf_counter() - t4) * 1000, 2),
        })
        if on_progress is not None:
            on_progress("upsert", 1, 1)

        if self._integrity is not None and not force:
            if file_hash is None:
                file_hash = self._integrity.compute_sha256(path)
            self._integrity.mark_success(file_hash, path)

        trace.finish()
        return {
            "document_id": document.id,
            "chunks_count": len(chunks),
            "records_count": len(records),
        }

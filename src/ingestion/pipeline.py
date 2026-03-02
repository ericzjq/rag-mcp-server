"""
Pipeline（C14）：串行执行 integrity→load→split→transform→encode→store，失败步骤抛出清晰异常。
"""

import logging
from pathlib import Path
from typing import Any, List, Optional

from core.settings import Settings
from core.trace.trace_context import TraceContext
from core.types import Chunk, Document

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
        self._transforms = transforms if transforms is not None else [
            ChunkRefiner(settings),
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
    ) -> dict:
        """
        对单文件执行完整摄取；失败时抛出明确异常。

        Args:
            path: 文档路径（如 PDF）。
            collection: 可选集合名（用于图片登记）。
            force: 若 True 跳过 integrity 检查强制重新摄取。
            batch_size: 编码批大小。
            trace: 可选追踪上下文。

        Returns:
            摘要 dict：document_id, chunks_count, records_count 等。
        """
        trace = trace or TraceContext()
        if not path or not Path(path).exists():
            raise FileNotFoundError(f"文档不存在: {path}")

        # 1. Integrity
        if self._integrity is not None and not force:
            file_hash = self._integrity.compute_sha256(path)
            if self._integrity.should_skip(file_hash):
                logger.info("跳过已摄取文件 (hash=%s): %s", file_hash[:8], path)
                return {"skipped": True, "file_hash": file_hash[:16]}

        # 2. Load
        logger.info("加载文档: %s", path)
        document = self._loader.load(path)
        trace.record_stage("load", {"document_id": document.id})

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
        chunks = self._chunker.split_document(document, trace=trace)
        if not chunks:
            logger.warning("文档分块为空: %s", path)
            if self._integrity is not None and not force:
                file_hash = self._integrity.compute_sha256(path)
                self._integrity.mark_success(file_hash, path)
            return {"document_id": document.id, "chunks_count": 0, "records_count": 0}
        trace.record_stage("split", {"chunks_count": len(chunks)})

        # 5. Transform
        for i, t in enumerate(self._transforms):
            chunks = t.transform(chunks, trace=trace)
        trace.record_stage("transform", {"chunks_count": len(chunks)})

        # 6. Encode
        logger.info("编码: %d chunks", len(chunks))
        records = self._batch_processor.process(chunks, batch_size=batch_size, trace=trace)
        trace.record_stage("encode", {"records_count": len(records)})

        # 7. Store
        logger.info("写入向量与 BM25 索引")
        self._vector_upserter.upsert(records, trace=trace)
        indexer = BM25Indexer(index_dir=self._bm25_index_dir)
        indexer.build(records).save()

        if self._integrity is not None and not force:
            file_hash = self._integrity.compute_sha256(path)
            self._integrity.mark_success(file_hash, path)

        return {
            "document_id": document.id,
            "chunks_count": len(chunks),
            "records_count": len(records),
        }

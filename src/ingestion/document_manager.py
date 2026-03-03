"""
DocumentManager（G2）：跨存储的文档生命周期管理（list/delete/stats）。
协调 ChromaStore、BM25Indexer、ImageStorage、FileIntegrityChecker。
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from libs.loader.file_integrity import FileIntegrityChecker
from libs.vector_store.base_vector_store import BaseVectorStore

from ingestion.storage.bm25_indexer import BM25Indexer
from ingestion.storage.image_storage import ImageStorage


def _doc_id_from_path(path: str) -> str:
    """与 PdfLoader 一致的文档 ID：path 的 SHA256 前 16 位。"""
    return hashlib.sha256(Path(path).resolve().as_posix().encode()).hexdigest()[:16]


@dataclass
class DocumentInfo:
    """已摄入文档的简要信息。"""
    source_path: str
    doc_id: str
    chunk_count: int
    image_count: int


@dataclass
class DocumentDetail:
    """单文档详情：chunk 列表（id、text、metadata）与关联图片。"""
    source_path: str
    doc_id: str
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DeleteResult:
    """删除文档的结果。"""
    source_path: str
    chroma_deleted: int
    bm25_removed: int
    images_deleted: int
    integrity_removed: bool


@dataclass
class CollectionStats:
    """集合级统计。"""
    document_count: int
    chunk_count: int
    image_count: int


class DocumentManager:
    """跨 Chroma、BM25、ImageStorage、FileIntegrity 的文档列表/详情/删除/统计。"""

    def __init__(
        self,
        chroma_store: BaseVectorStore,
        bm25_indexer: BM25Indexer,
        image_storage: ImageStorage,
        file_integrity: FileIntegrityChecker,
    ) -> None:
        self._chroma = chroma_store
        self._bm25 = bm25_indexer
        self._images = image_storage
        self._integrity = file_integrity

    def list_documents(self, collection: Optional[str] = None) -> List[DocumentInfo]:
        """
        列出已摄入文档（source_path、chunk 数、图片数）。
        collection 可选：为 None 时返回全部；否则仅返回在该 collection 下有图片的文档。
        """
        processed = getattr(self._integrity, "list_processed", None)
        if not processed or not callable(processed):
            return []
        all_pairs: List[tuple] = processed()
        if not all_pairs:
            return []
        # (file_path, file_hash) from list_processed
        if collection:
            coll_doc_hashes = set()
            for row in self._images.list_by_collection(collection):
                dh = row.get("doc_hash")
                if dh:
                    coll_doc_hashes.add(dh)
            if not coll_doc_hashes:
                return []
            out: List[DocumentInfo] = []
            for file_path, _ in all_pairs:
                doc_id = _doc_id_from_path(file_path)
                if doc_id not in coll_doc_hashes:
                    continue
                chunk_ids = self._chroma.get_ids_by_metadata({"source_path": file_path})
                img_rows = self._images.list_by_doc_hash(doc_id)
                out.append(
                    DocumentInfo(
                        source_path=file_path,
                        doc_id=doc_id,
                        chunk_count=len(chunk_ids),
                        image_count=len(img_rows),
                    )
                )
            return out
        out = []
        for file_path, _ in all_pairs:
            doc_id = _doc_id_from_path(file_path)
            chunk_ids = self._chroma.get_ids_by_metadata({"source_path": file_path})
            img_rows = self._images.list_by_doc_hash(doc_id)
            out.append(
                DocumentInfo(
                    source_path=file_path,
                    doc_id=doc_id,
                    chunk_count=len(chunk_ids),
                    image_count=len(img_rows),
                )
            )
        return out

    def get_document_detail(self, doc_id: str) -> Optional[DocumentDetail]:
        """获取单文档详情：所有 chunk（id、text、metadata）与关联图片。"""
        processed = getattr(self._integrity, "list_processed", None)
        if not processed or not callable(processed):
            return None
        source_path: Optional[str] = None
        for file_path, _ in processed():
            if _doc_id_from_path(file_path) == doc_id:
                source_path = file_path
                break
        if not source_path:
            return None
        chunk_ids = self._chroma.get_ids_by_metadata({"source_path": source_path})
        if not chunk_ids:
            chunks_data: List[Dict[str, Any]] = []
        else:
            raw = self._chroma.get_by_ids(chunk_ids)
            chunks_data = [{"id": r["id"], "text": r.get("text", ""), "metadata": r.get("metadata", {})} for r in raw]
        img_rows = self._images.list_by_doc_hash(doc_id)
        return DocumentDetail(
            source_path=source_path,
            doc_id=doc_id,
            chunks=chunks_data,
            images=img_rows,
        )

    def delete_document(self, source_path: str, collection: str = "") -> DeleteResult:
        """协调删除 Chroma、BM25、ImageStorage、FileIntegrity 中与该文档相关的数据。"""
        doc_id = _doc_id_from_path(source_path)
        chunk_ids = self._chroma.get_ids_by_metadata({"source_path": source_path})
        chroma_deleted = self._chroma.delete_by_metadata({"source_path": source_path})

        bm25_removed = 0
        if chunk_ids and hasattr(self._bm25, "remove_document"):
            try:
                self._bm25.load()
            except (FileNotFoundError, OSError):
                pass
            bm25_removed = self._bm25.remove_document(chunk_ids)

        images_deleted = self._images.delete_by_doc_hash(doc_id)

        try:
            file_hash = self._integrity.compute_sha256(source_path)
            integrity_removed = getattr(self._integrity, "remove_record", lambda _: False)(file_hash)
        except FileNotFoundError:
            # 文件已不存在（如 Dashboard 上传的临时文件已被清理），按 path 从 integrity 表移除
            integrity_removed = getattr(self._integrity, "remove_record_by_path", lambda _: False)(source_path)

        return DeleteResult(
            source_path=source_path,
            chroma_deleted=chroma_deleted,
            bm25_removed=bm25_removed,
            images_deleted=images_deleted,
            integrity_removed=integrity_removed,
        )

    def get_collection_stats(self, collection: Optional[str] = None) -> CollectionStats:
        """返回集合级统计：文档数、chunk 数、图片数。"""
        docs = self.list_documents(collection=collection)
        document_count = len(docs)
        chunk_count = sum(d.chunk_count for d in docs)
        image_count = sum(d.image_count for d in docs)
        return CollectionStats(
            document_count=document_count,
            chunk_count=chunk_count,
            image_count=image_count,
        )

"""
VectorUpserter（C12）：接收 DenseEncoder 的向量输出，生成稳定 chunk_id，调用 VectorStore 幂等写入。
"""

import hashlib
import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

from core.types import ChunkRecord

from libs.vector_store.base_vector_store import BaseVectorStore, VectorStoreRecord


def compute_stable_id(record: ChunkRecord) -> str:
    """
    生成确定性 chunk_id，与 file_hash 去重一致：
    - 若有 file_hash：id = SHA256(file_hash + chunk_index)，同一文件任意 path 得到相同 id。
    - 否则回退：id = SHA256(source_path + chunk_index + content_hash[:8])，兼容未写 file_hash 的旧逻辑。
    """
    meta = record.metadata or {}
    file_hash = meta.get("file_hash")
    chunk_index = meta.get("chunk_index")
    if chunk_index is None:
        chunk_index = 0
    else:
        chunk_index = int(chunk_index)
    if file_hash:
        key = f"{file_hash}{chunk_index}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
    source_path = str(meta.get("source_path", ""))
    content_hash = hashlib.sha256((record.text or "").encode("utf-8")).hexdigest()[:8]
    key = f"{source_path}{chunk_index}{content_hash}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class VectorUpserter:
    """将 ChunkRecord（含 dense_vector）转为稳定 id 并批量 upsert 到 VectorStore，保证幂等。"""

    def __init__(self, vector_store: BaseVectorStore) -> None:
        self._store = vector_store

    def upsert(
        self,
        records: List[ChunkRecord],
        trace: Optional[Any] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        为每条 record 生成稳定 id，调用 VectorStore.upsert；同一内容重复写入产生相同 id（幂等）。
        C16：删除前先收集将被删的 id，返回 (stored_ids, deleted_ids) 供 BM25 增量更新使用。

        Args:
            records: 含 dense_vector 的 ChunkRecord 列表（顺序保持）。
            trace: 可选追踪上下文。

        Returns:
            (写入使用的 id 列表与 records 顺序一致, 本轮删除的 chunk_id 列表，供 BM25 remove_document)。
        """
        if not records:
            return ([], [])
        first_meta = records[0].metadata or {}
        file_hash = first_meta.get("file_hash")
        source_path = first_meta.get("source_path")
        deleted_ids: List[str] = []
        if hasattr(self._store, "get_ids_by_metadata") and hasattr(self._store, "delete_by_metadata"):
            deleted_set: set = set()
            if file_hash:
                deleted_set.update(self._store.get_ids_by_metadata({"file_hash": file_hash}))
            if source_path:
                deleted_set.update(self._store.get_ids_by_metadata({"source_path": source_path}))
            deleted_ids = list(deleted_set)
            if deleted_ids:
                logger.info("按 file_hash/source_path 将删除旧 chunk 数量: %d", len(deleted_ids))
            if file_hash:
                self._store.delete_by_metadata({"file_hash": file_hash})
            if source_path:
                self._store.delete_by_metadata({"source_path": source_path})
        store_records: List[VectorStoreRecord] = []
        ids: List[str] = []
        for r in records:
            sid = compute_stable_id(r)
            ids.append(sid)
            if r.dense_vector is not None:
                meta = dict(r.metadata) if r.metadata else {}
                meta["text"] = r.text  # ChromaStore 需要 documents 来自 metadata.text
                store_records.append({
                    "id": sid,
                    "vector": list(r.dense_vector),
                    "metadata": meta,
                })
        if store_records:
            self._store.upsert(store_records, trace=trace)
        return (ids, deleted_ids)

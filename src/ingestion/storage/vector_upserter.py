"""
VectorUpserter（C12）：接收 DenseEncoder 的向量输出，生成稳定 chunk_id，调用 VectorStore 幂等写入。
"""

import hashlib
from typing import Any, List, Optional

from core.types import ChunkRecord

from libs.vector_store.base_vector_store import BaseVectorStore, VectorStoreRecord


def compute_stable_id(record: ChunkRecord) -> str:
    """
    生成确定性 chunk_id：hash(source_path + chunk_index + content_hash[:8])。

    从 record.metadata 取 source_path、chunk_index，对 record.text 做 SHA256 取前 8 字符为 content_hash，
    再对拼接串做 SHA256 取 hex 作为 id。
    """
    meta = record.metadata or {}
    source_path = str(meta.get("source_path", ""))
    chunk_index = meta.get("chunk_index")
    if chunk_index is None:
        chunk_index = 0
    else:
        chunk_index = int(chunk_index)
    content_hash = hashlib.sha256(record.text.encode("utf-8")).hexdigest()[:8]
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
    ) -> List[str]:
        """
        为每条 record 生成稳定 id，调用 VectorStore.upsert；同一内容重复写入产生相同 id（幂等）。

        Args:
            records: 含 dense_vector 的 ChunkRecord 列表（顺序保持）。
            trace: 可选追踪上下文。

        Returns:
            写入使用的 id 列表，与 records 顺序一致。
        """
        if not records:
            return []
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
        return ids

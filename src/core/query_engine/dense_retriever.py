"""
DenseRetriever（D2）：query 向量化 + VectorStore 检索，返回 RetrievalResult 列表。
"""

import time
from typing import Any, List, Optional

from core.settings import Settings
from core.types import RetrievalResult

from libs.embedding.base_embedding import BaseEmbedding
from libs.embedding.embedding_factory import create as create_embedding
from libs.vector_store.base_vector_store import BaseVectorStore
from libs.vector_store.vector_store_factory import create as create_vector_store


class DenseRetriever:
    """组合 EmbeddingClient（query 向量化）与 VectorStore，完成语义召回。"""

    def __init__(
        self,
        settings: Settings,
        *,
        embedding_client: Optional[BaseEmbedding] = None,
        vector_store: Optional[BaseVectorStore] = None,
    ) -> None:
        self._settings = settings
        self._embedding = embedding_client if embedding_client is not None else create_embedding(settings)
        self._store = vector_store if vector_store is not None else create_vector_store(settings)

    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: Optional[dict] = None,
        trace: Optional[Any] = None,
    ) -> List[RetrievalResult]:
        """
        对 query 做向量检索，返回有序 RetrievalResult 列表。

        Args:
            query: 用户查询字符串。
            top_k: 返回条数。
            filters: 可选 metadata 过滤。
            trace: 可选追踪上下文。

        Returns:
            含 chunk_id、score、text、metadata 的列表。
        """
        if not (query or "").strip():
            return []
        t0 = time.perf_counter()
        vectors = self._embedding.embed([query.strip()], trace=trace)
        t1 = time.perf_counter()
        if not vectors:
            return []
        items = self._store.query(vectors[0], top_k, filters=filters, trace=trace)
        t2 = time.perf_counter()
        if trace is not None:
            trace.record_stage("dense_retrieval_breakdown", {
                "embed_ms": round((t1 - t0) * 1000, 2),
                "query_ms": round((t2 - t1) * 1000, 2),
            })
        return [
            RetrievalResult(
                chunk_id=item["id"],
                score=float(item.get("score", 0.0)),
                text=item.get("text", ""),
                metadata=dict(item.get("metadata", {})),
            )
            for item in items
        ]

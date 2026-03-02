"""
HybridSearch（D5）：编排 QueryProcessor + Dense + Sparse + Fusion，支持 filters 与单路降级。
"""

import logging
from typing import Any, Callable, List, Optional

from core.settings import Settings
from core.types import RetrievalResult

from core.query_engine.dense_retriever import DenseRetriever
from core.query_engine.fusion import rrf_fuse, DEFAULT_RRF_K
from core.query_engine.query_processor import ProcessedQuery, QueryProcessor
from core.query_engine.sparse_retriever import SparseRetriever

logger = logging.getLogger(__name__)

# 每路召回数放大倍数，便于融合后仍有足够候选
_RETRIEVE_MULTIPLIER = 3


class HybridSearch:
    """混合检索：query_processor → dense + sparse（任一路失败则降级）→ fusion → metadata_filter → Top-K。"""

    def __init__(
        self,
        settings: Settings,
        *,
        query_processor: Optional[QueryProcessor] = None,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        fusion_fn: Optional[Callable[..., List[RetrievalResult]]] = None,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self._settings = settings
        self._qp = query_processor if query_processor is not None else QueryProcessor()
        self._dense = dense_retriever if dense_retriever is not None else DenseRetriever(settings)
        self._sparse = sparse_retriever if sparse_retriever is not None else SparseRetriever(settings)
        self._fusion_fn = fusion_fn if fusion_fn is not None else rrf_fuse
        self._rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int,
        filters: Optional[dict] = None,
        trace: Optional[Any] = None,
    ) -> List[RetrievalResult]:
        """
        执行混合检索：process(query) → dense.retrieve + sparse.retrieve（任一路失败降级）→ fuse → metadata_filter → Top-K。

        Args:
            query: 用户查询。
            top_k: 返回条数。
            filters: 可选 metadata 过滤（同时传 VectorStore 与后置过滤）。
            trace: 可选追踪上下文。

        Returns:
            RetrievalResult 列表，含 chunk 文本与 metadata。
        """
        if not (query or "").strip():
            return []
        processed = self._qp.process(query.strip())
        fetch_k = max(top_k, 1) * _RETRIEVE_MULTIPLIER
        dense_list: List[RetrievalResult] = []
        sparse_list: List[RetrievalResult] = []
        try:
            dense_list = self._dense.retrieve(query, fetch_k, filters=filters, trace=trace)
        except Exception as e:
            logger.warning("Dense 检索失败，将仅用 Sparse 结果: %s", e)
        try:
            sparse_list = self._sparse.retrieve(processed.keywords, fetch_k, trace=trace)
        except Exception as e:
            logger.warning("Sparse 检索失败，将仅用 Dense 结果: %s", e)
        if dense_list and sparse_list:
            fused = self._fusion_fn([dense_list, sparse_list], k=self._rrf_k)
        elif dense_list:
            fused = dense_list
        elif sparse_list:
            fused = sparse_list
        else:
            return []
        filtered = self._apply_metadata_filters(fused, filters)
        return filtered[:top_k]

    def _apply_metadata_filters(
        self,
        candidates: List[RetrievalResult],
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        """后置过滤：仅保留 metadata 满足 filters 的候选（filters 为空则全部保留）。"""
        if not filters:
            return list(candidates)
        out: List[RetrievalResult] = []
        for c in candidates:
            if all(c.metadata.get(k) == v for k, v in filters.items()):
                out.append(c)
        return out

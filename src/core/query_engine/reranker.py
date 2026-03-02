"""
Reranker（D6）：Core 层编排，接入 libs.reranker 后端；失败/超时回退 fusion 排名并标记 fallback。F3 打点。
"""

import logging
import time
from typing import Any, List, Optional

from core.settings import Settings
from core.types import RetrievalResult

from libs.reranker.base_reranker import BaseReranker, RerankCandidate
from libs.reranker.reranker_factory import create as create_reranker

logger = logging.getLogger(__name__)


def _to_candidates(results: List[RetrievalResult]) -> List[RerankCandidate]:
    """RetrievalResult → RerankCandidate（id, score, text, metadata）。"""
    return [
        {"id": r.chunk_id, "score": r.score, "text": r.text, "metadata": dict(r.metadata)}
        for r in results
    ]


def _from_candidates(candidates: List[RerankCandidate]) -> List[RetrievalResult]:
    """RerankCandidate → RetrievalResult。"""
    return [
        RetrievalResult(
            chunk_id=c["id"],
            score=float(c.get("score", 0.0)),
            text=c.get("text", ""),
            metadata=dict(c.get("metadata", {})),
        )
        for c in candidates
    ]


class Reranker:
    """对接 libs BaseReranker；异常时返回原序并标记 metadata['rerank_fallback']=True。"""

    def __init__(
        self,
        settings: Settings,
        *,
        backend: Optional[BaseReranker] = None,
    ) -> None:
        self._settings = settings
        self._backend = backend if backend is not None else create_reranker(settings)

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        trace: Optional[Any] = None,
    ) -> List[RetrievalResult]:
        """
        对候选做精排；后端异常时返回原序并在每条结果的 metadata 中设置 rerank_fallback=True。

        Args:
            query: 查询文本。
            candidates: 粗排候选（如 fusion 输出）。
            trace: 可选追踪上下文。

        Returns:
            精排后的 RetrievalResult 列表；若发生回退则顺序不变且 metadata 含 rerank_fallback=True。
        """
        if not candidates:
            return []
        t0 = time.perf_counter()
        try:
            raw = _to_candidates(candidates)
            out = self._backend.rerank(query, raw, trace=trace)
            result = _from_candidates(out)
        except Exception as e:
            logger.warning("Reranker 后端异常，回退到 fusion 排名: %s", e)
            result = [
                RetrievalResult(
                    chunk_id=r.chunk_id,
                    score=r.score,
                    text=r.text,
                    metadata=dict(r.metadata, rerank_fallback=True),
                )
                for r in candidates
            ]
        if trace is not None:
            trace.record_stage("rerank", {
                "method": getattr(self._settings.rerank, "provider", "reranker"),
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            })
        return result

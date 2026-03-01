"""
NoneReranker：不改变排序，作为默认回退。

当配置 rerank.provider=none 或精排不可用时使用，保持粗排（如 RRF）的原有顺序。
"""

from typing import Any, List, Optional

from core.settings import Settings

from libs.reranker.base_reranker import BaseReranker, RerankCandidate


class NoneReranker(BaseReranker):
    """保持原顺序的 Reranker，用于 backend=none 或回退场景。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def rerank(
        self,
        query: str,
        candidates: List[RerankCandidate],
        trace: Optional[Any] = None,
    ) -> List[RerankCandidate]:
        """原样返回候选列表，不改变顺序。"""
        return list(candidates)

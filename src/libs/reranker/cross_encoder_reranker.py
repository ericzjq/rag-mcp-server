"""
Cross-Encoder Reranker：对 Top-M 候选用 scorer 打分并排序；超时/失败时回退为原序。
"""

from typing import Any, Callable, List, Optional

from core.settings import Settings

from libs.reranker.base_reranker import BaseReranker, RerankCandidate

# 打分函数类型：(query, candidates) -> 与 candidates 等长的分数列表
ScorerFn = Callable[[str, List[RerankCandidate]], List[float]]


class CrossEncoderReranker(BaseReranker):
    """使用 Cross-Encoder 或注入的 scorer 对候选打分排序；异常/超时则回退原序。"""

    def __init__(
        self,
        settings: Settings,
        *,
        scorer: Optional[ScorerFn] = None,
    ) -> None:
        self._settings = settings
        self._scorer = scorer

    def _get_scorer(self) -> ScorerFn:
        if self._scorer is not None:
            return self._scorer
        # 占位：未注入 scorer 且未配置模型时，回退由 rerank 内 try 统一处理
        def _placeholder(query: str, candidates: List[RerankCandidate]) -> List[float]:
            raise NotImplementedError(
                "CrossEncoderReranker: 未注入 scorer，且未配置本地/托管模型；请注入 scorer 或后续配置模型"
            )
        return _placeholder

    def rerank(
        self,
        query: str,
        candidates: List[RerankCandidate],
        trace: Optional[Any] = None,
    ) -> List[RerankCandidate]:
        if not candidates:
            return []
        try:
            scorer = self._get_scorer()
            scores = scorer(query, candidates)
            if len(scores) != len(candidates):
                return list(candidates)
            # 按分数降序排列，分数相同保持原序
            indexed = list(zip(scores, range(len(candidates)), candidates))
            indexed.sort(key=lambda x: (-x[0], x[1]))
            return [x[2] for x in indexed]
        except Exception:
            # 超时/失败回退：返回原序，供 Core 层 D6 fallback 使用
            return list(candidates)

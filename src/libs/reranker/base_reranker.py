"""
Reranker 抽象基类。

对粗排候选进行精排；NoneReranker 保持原顺序作为默认回退，CrossEncoder/LLM 等为可选增强。
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


# 候选项：至少含 "id", "score"，可选 "metadata"/"text" 等
RerankCandidate = dict  # Dict[str, Any]


class BaseReranker(ABC):
    """Reranker 抽象基类，统一 rerank 接口。"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List[RerankCandidate],
        trace: Optional[Any] = None,
    ) -> List[RerankCandidate]:
        """
        对候选列表重新排序（精排）。

        Args:
            query: 查询文本。
            candidates: 候选列表，每项至少含 "id" (str)、"score" (float)，可选 "metadata"/"text"。
            trace: 可选追踪上下文，当前可传 None。

        Returns:
            重排后的候选列表（同类型，顺序可能改变）。
        """
        ...

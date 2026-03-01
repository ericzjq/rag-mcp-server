"""
Evaluator 抽象基类。

评估检索/生成质量；CustomEvaluator 提供 hit_rate/mrr 等轻量指标，Ragas 等为可选扩展。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseEvaluator(ABC):
    """Evaluator 抽象基类，统一 evaluate 接口。"""

    @abstractmethod
    def evaluate(
        self,
        query: str,
        retrieved_ids: List[str],
        golden_ids: List[str],
        trace: Optional[Any] = None,
    ) -> Dict[str, float]:
        """
        根据 query、检索结果 id 列表与标准答案 id 列表计算指标。

        Args:
            query: 查询文本。
            retrieved_ids: 检索返回的 chunk id 列表（按相关度排序）。
            golden_ids: 标准答案/相关 chunk id 列表。
            trace: 可选追踪上下文，当前可传 None。

        Returns:
            指标字典，如 {"hit_rate": 0.0~1.0, "mrr": 0.0~1.0}，键名稳定便于汇总。
        """
        ...

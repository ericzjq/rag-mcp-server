"""
CustomEvaluator：轻量自定义指标（hit_rate、mrr）。

不依赖 Ragas/LLM，输入 query + retrieved_ids + golden_ids 输出稳定 metrics。
"""

from typing import Any, Dict, List, Optional

from core.settings import Settings

from libs.evaluator.base_evaluator import BaseEvaluator


def _hit_rate_one(retrieved_ids: List[str], golden_ids: List[str]) -> float:
    """单条：检索结果中是否命中任一 golden，命中为 1.0 否则 0.0。"""
    if not golden_ids:
        return 0.0
    return 1.0 if any(rid in golden_ids for rid in retrieved_ids) else 0.0


def _mrr_one(retrieved_ids: List[str], golden_ids: List[str]) -> float:
    """单条：第一个命中的 golden 的倒数排名，未命中为 0.0。"""
    if not golden_ids:
        return 0.0
    for i, rid in enumerate(retrieved_ids):
        if rid in golden_ids:
            return 1.0 / (i + 1)
    return 0.0


class CustomEvaluator(BaseEvaluator):
    """自定义轻量评估器：hit_rate、mrr。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def evaluate(
        self,
        query: str,
        retrieved_ids: List[str],
        golden_ids: List[str],
        trace: Optional[Any] = None,
    ) -> Dict[str, float]:
        """计算 hit_rate（是否命中）与 mrr（首位命中排名倒数）。"""
        hit = _hit_rate_one(retrieved_ids, golden_ids)
        mrr = _mrr_one(retrieved_ids, golden_ids)
        return {"hit_rate": hit, "mrr": mrr}

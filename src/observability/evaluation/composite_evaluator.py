"""
CompositeEvaluator（H2）：组合多个 BaseEvaluator，并行执行并合并 metrics。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from libs.evaluator.base_evaluator import BaseEvaluator


def _prefix_key(prefix: str, key: str) -> str:
    """生成带前缀的指标键，避免多 evaluator 合并时冲突。"""
    return f"{prefix}_{key}" if prefix else key


class CompositeEvaluator(BaseEvaluator):
    """组合多个评估器：并行调用各 evaluator.evaluate()，合并返回的 metrics。"""

    def __init__(self, evaluators: List[BaseEvaluator]) -> None:
        """
        Args:
            evaluators: 子评估器列表，不可为空。
        """
        if not evaluators:
            raise ValueError("CompositeEvaluator 至少需要一个子 evaluator")
        self._evaluators = list(evaluators)

    def evaluate(
        self,
        query: str,
        retrieved_ids: List[str],
        golden_ids: List[str],
        trace: Optional[Any] = None,
    ) -> Dict[str, float]:
        """并行执行所有子 evaluator，合并其返回的 metrics（键加类型前缀避免冲突）。"""
        merged: Dict[str, float] = {}
        max_workers = min(len(self._evaluators), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ev = {
                executor.submit(ev.evaluate, query, retrieved_ids, golden_ids, trace): ev
                for ev in self._evaluators
            }
            for future in as_completed(future_to_ev):
                ev = future_to_ev[future]
                try:
                    metrics = future.result()
                except Exception:
                    continue
                # 前缀：类名去掉尾随 Evaluator 及前导下划线，如 CustomEvaluator -> custom
                name = type(ev).__name__.lower()
                prefix = name.replace("evaluator", "").strip().lstrip("_") or name
                for k, v in (metrics or {}).items():
                    if isinstance(v, (int, float)):
                        merged[_prefix_key(prefix, k)] = float(v)
        return merged

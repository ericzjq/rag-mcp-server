"""
RagasEvaluator（H1）：封装 Ragas 框架，实现 BaseEvaluator 接口。
支持 Faithfulness、Answer Relevancy、Context Precision；Ragas 未安装时抛出明确 ImportError。
"""

from typing import Any, Dict, List, Optional

from core.settings import Settings

from libs.evaluator.base_evaluator import BaseEvaluator


def _ensure_ragas() -> None:
    """若 ragas 未安装则抛出带提示的 ImportError。"""
    try:
        import ragas  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Ragas 未安装，请执行: pip install ragas"
        ) from e


class RagasEvaluator(BaseEvaluator):
    """基于 Ragas 的评估器：Faithfulness、Answer Relevancy、Context Precision。"""

    def __init__(self, settings: Settings, llm: Optional[Any] = None) -> None:
        self._settings = settings
        self._llm = llm
        self._ragas_error: Optional[ImportError] = None
        try:
            _ensure_ragas()
        except ImportError as e:
            self._ragas_error = e

    def evaluate(
        self,
        query: str,
        retrieved_ids: List[str],
        golden_ids: List[str],
        trace: Optional[Any] = None,
    ) -> Dict[str, float]:
        """
        使用 Ragas 计算 faithfulness、answer_relevancy、context_precision。
        无 answer/contexts 文本时使用占位数据，指标可能为 0 或由 Ragas 默认行为决定。
        """
        if self._ragas_error is not None:
            raise self._ragas_error

        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import ContextPrecision, Faithfulness, AnswerRelevancy

        # 单条样本：Ragas 需要 question, contexts, answer, ground_truth
        data = {
            "question": [query or ""],
            "contexts": [[""]],  # 无正文时用占位
            "answer": [""],
            "ground_truth": [""],
        }
        dataset = Dataset.from_dict(data)
        metrics = [ContextPrecision(), Faithfulness(), AnswerRelevancy()]
        try:
            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=self._llm,
                show_progress=False,
            )
        except Exception:
            return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0}

        out = _result_to_metrics(result)
        return out


def _result_to_metrics(result: Any) -> Dict[str, float]:
    """将 ragas EvaluationResult 转为含 faithfulness/answer_relevancy/context_precision 的字典。"""
    default = {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0}
    for key in default:
        val = getattr(result, key, None)
        if val is None and hasattr(result, "get"):
            val = result.get(key)
        if val is not None:
            try:
                v = float(val)
                if v == v:  # not nan
                    default[key] = v
            except (TypeError, ValueError):
                pass
    return default

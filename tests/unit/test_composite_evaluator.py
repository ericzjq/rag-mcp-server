"""
CompositeEvaluator 单元测试（H2）：组合多个 evaluator，返回的 metrics 包含两者的指标。
"""

from typing import Any, Dict, List, Optional

import pytest

from core.settings import (
    EmbeddingSettings,
    EvaluationSettings,
    LlmSettings,
    ObservabilitySettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    SplitterSettings,
    VectorStoreSettings,
)
from libs.evaluator.base_evaluator import BaseEvaluator
from libs.evaluator.custom_evaluator import CustomEvaluator
from observability.evaluation.composite_evaluator import CompositeEvaluator


def _make_settings() -> Settings:
    """构建用于测试的 Settings。"""
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="custom"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class _FakeEvaluator(BaseEvaluator):
    """测试用：固定返回一组指标。"""

    def evaluate(
        self,
        query: str,
        retrieved_ids: List[str],
        golden_ids: List[str],
        trace: Optional[Any] = None,
    ) -> Dict[str, float]:
        return {"score_x": 1.0, "score_y": 0.5}


def test_composite_empty_evaluators_raises() -> None:
    """evaluators 为空时 __init__ 抛出 ValueError。"""
    with pytest.raises(ValueError) as exc_info:
        CompositeEvaluator([])
    assert "至少" in str(exc_info.value) or "evaluator" in str(exc_info.value).lower()


def test_composite_evaluate_returns_merged_metrics_from_two_evaluators() -> None:
    """配置两个 evaluator 时，返回的 metrics 包含两者的指标。"""
    settings = _make_settings()
    custom = CustomEvaluator(settings)
    fake = _FakeEvaluator()
    composite = CompositeEvaluator([custom, fake])
    metrics = composite.evaluate(
        query="test",
        retrieved_ids=["a", "b"],
        golden_ids=["b"],
        trace=None,
    )
    # CustomEvaluator 产出 hit_rate, mrr -> 带 custom_ 前缀
    assert "custom_hit_rate" in metrics
    assert "custom_mrr" in metrics
    assert metrics["custom_hit_rate"] == 1.0
    assert metrics["custom_mrr"] == 0.5
    # _FakeEvaluator 产出 score_x, score_y -> 带 fake_ 前缀（类名 _FakeEvaluator -> fake）
    assert "fake_score_x" in metrics
    assert "fake_score_y" in metrics
    assert metrics["fake_score_x"] == 1.0
    assert metrics["fake_score_y"] == 0.5


def test_composite_single_evaluator() -> None:
    """单个 evaluator 时合并结果仍带前缀。"""
    settings = _make_settings()
    composite = CompositeEvaluator([CustomEvaluator(settings)])
    metrics = composite.evaluate("q", ["a"], ["a"], trace=None)
    assert "custom_hit_rate" in metrics
    assert "custom_mrr" in metrics
    assert metrics["custom_hit_rate"] == 1.0

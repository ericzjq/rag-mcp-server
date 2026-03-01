"""
CustomEvaluator 单元测试：输入 query + retrieved_ids + golden_ids 输出稳定 metrics。
"""

from typing import Any, List, Optional

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
from libs.evaluator.custom_evaluator import CustomEvaluator
from libs.evaluator.evaluator_factory import create


def _make_settings(evaluation_provider: str = "custom") -> Settings:
    """构建用于测试的 Settings。"""
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider=evaluation_provider),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_evaluate_returns_hit_rate_and_mrr() -> None:
    """evaluate 返回包含 hit_rate、mrr 的稳定 metrics。"""
    ev = CustomEvaluator(_make_settings())
    metrics = ev.evaluate(
        query="test",
        retrieved_ids=["a", "b", "c"],
        golden_ids=["b", "x"],
        trace=None,
    )
    assert "hit_rate" in metrics
    assert "mrr" in metrics
    assert metrics["hit_rate"] == 1.0  # b 命中
    assert metrics["mrr"] == 0.5  # b 在 rank 2 -> 1/2


def test_evaluate_no_hit() -> None:
    """检索结果无命中时 hit_rate=0, mrr=0。"""
    ev = CustomEvaluator(_make_settings())
    metrics = ev.evaluate(
        query="test",
        retrieved_ids=["a", "b"],
        golden_ids=["x", "y"],
        trace=None,
    )
    assert metrics["hit_rate"] == 0.0
    assert metrics["mrr"] == 0.0


def test_evaluate_first_rank_mrr_one() -> None:
    """第一个即为命中时 mrr=1.0。"""
    ev = CustomEvaluator(_make_settings())
    metrics = ev.evaluate(
        query="q",
        retrieved_ids=["g1", "g2"],
        golden_ids=["g1"],
        trace=None,
    )
    assert metrics["hit_rate"] == 1.0
    assert metrics["mrr"] == 1.0


def test_factory_create_custom() -> None:
    """provider=custom 时工厂返回 CustomEvaluator。"""
    evaluator = create(_make_settings(evaluation_provider="custom"))
    assert isinstance(evaluator, CustomEvaluator)
    m = evaluator.evaluate("q", ["a"], ["a"], trace=None)
    assert m["hit_rate"] == 1.0 and m["mrr"] == 1.0


def test_factory_unknown_provider_raises() -> None:
    """未知 provider 时抛出 ValueError。"""
    with pytest.raises(ValueError) as exc_info:
        create(_make_settings(evaluation_provider="unknown_eval"))
    assert "unknown_eval" in str(exc_info.value)

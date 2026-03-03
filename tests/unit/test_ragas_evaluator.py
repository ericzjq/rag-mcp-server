"""
RagasEvaluator 单元测试（H1）：未安装时 ImportError；mock 下 evaluate 返回 faithfulness/answer_relevancy。
"""

from unittest.mock import MagicMock, patch

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
from libs.evaluator.evaluator_factory import create
from observability.evaluation.ragas_evaluator import RagasEvaluator, _result_to_metrics


def _make_settings(evaluation_provider: str = "ragas") -> Settings:
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


def test_ragas_evaluate_raises_import_error_when_ragas_not_available() -> None:
    """Ragas 不可用时 evaluate() 抛出带明确提示的 ImportError。"""
    with patch(
        "observability.evaluation.ragas_evaluator._ensure_ragas",
        side_effect=ImportError("Ragas 未安装，请执行: pip install ragas"),
    ):
        ev = RagasEvaluator(_make_settings())
    with pytest.raises(ImportError) as exc_info:
        ev.evaluate(query="test", retrieved_ids=[], golden_ids=[], trace=None)
    assert "Ragas" in str(exc_info.value) or "pip install" in str(exc_info.value)


def test_result_to_metrics_returns_faithfulness_and_answer_relevancy() -> None:
    """_result_to_metrics 将 result 转为含 faithfulness、answer_relevancy、context_precision 的字典。"""
    mock_result = MagicMock()
    mock_result.faithfulness = 0.5
    mock_result.answer_relevancy = 0.6
    mock_result.context_precision = 0.7
    metrics = _result_to_metrics(mock_result)
    assert "faithfulness" in metrics
    assert "answer_relevancy" in metrics
    assert "context_precision" in metrics
    assert metrics["faithfulness"] == 0.5
    assert metrics["answer_relevancy"] == 0.6
    assert metrics["context_precision"] == 0.7


def test_factory_create_ragas_when_registered() -> None:
    """provider=ragas 且 ragas 已注册时工厂返回 RagasEvaluator。"""
    with patch("observability.evaluation.ragas_evaluator._ensure_ragas"):
        evaluator = create(_make_settings(evaluation_provider="ragas"))
    assert isinstance(evaluator, RagasEvaluator)

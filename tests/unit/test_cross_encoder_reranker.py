"""
Cross-Encoder Reranker 单元测试：mock scorer，验证工厂路由、按分数排序、失败回退。
"""

from typing import Any, List

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
from libs.reranker.base_reranker import RerankCandidate
from libs.reranker.cross_encoder_reranker import CrossEncoderReranker
from libs.reranker.reranker_factory import create


def _make_settings(rerank_provider: str = "cross_encoder") -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider=rerank_provider),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_returns_cross_encoder_reranker() -> None:
    """provider=cross_encoder 时 RerankerFactory 可创建 CrossEncoderReranker。"""
    settings = _make_settings(rerank_provider="cross_encoder")
    reranker = create(settings)
    assert isinstance(reranker, CrossEncoderReranker)


def test_rerank_with_mock_scorer_orders_by_score_desc() -> None:
    """Mock scorer 返回分数时，按分数降序重排（deterministic）。"""
    def mock_scorer(query: str, candidates: List[RerankCandidate]) -> List[float]:
        # 按 id 给固定分数，便于断言
        return [0.9 if c["id"] == "b" else 0.5 if c["id"] == "a" else 0.7 for c in candidates]
    settings = _make_settings()
    reranker = CrossEncoderReranker(settings, scorer=mock_scorer)
    candidates = [
        {"id": "a", "score": 0.5, "text": "A"},
        {"id": "b", "score": 0.9, "text": "B"},
        {"id": "c", "score": 0.3, "text": "C"},
    ]
    result = reranker.rerank("q", candidates, trace=None)
    assert [r["id"] for r in result] == ["b", "c", "a"]


def test_rerank_scorer_raises_fallback_to_original_order() -> None:
    """Scorer 抛出异常时回退为原序。"""
    def failing_scorer(query: str, candidates: List[RerankCandidate]) -> List[float]:
        raise RuntimeError("model timeout")
    settings = _make_settings()
    reranker = CrossEncoderReranker(settings, scorer=failing_scorer)
    candidates = [{"id": "x", "score": 0.5}, {"id": "y", "score": 0.9}]
    result = reranker.rerank("q", candidates, trace=None)
    assert result == candidates


def test_rerank_empty_candidates_returns_empty() -> None:
    """空候选返回空列表。"""
    settings = _make_settings()
    reranker = CrossEncoderReranker(settings, scorer=lambda q, c: [])
    result = reranker.rerank("q", [], trace=None)
    assert result == []


def test_rerank_score_length_mismatch_fallback() -> None:
    """Scorer 返回长度与 candidates 不一致时回退原序。"""
    def bad_scorer(query: str, candidates: List[RerankCandidate]) -> List[float]:
        return [1.0]  # 只有 1 个分数，candidates 有 2 个
    settings = _make_settings()
    reranker = CrossEncoderReranker(settings, scorer=bad_scorer)
    candidates = [{"id": "a", "score": 0.5}, {"id": "b", "score": 0.9}]
    result = reranker.rerank("q", candidates, trace=None)
    assert result == candidates

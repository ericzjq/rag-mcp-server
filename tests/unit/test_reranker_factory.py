"""
Reranker 工厂单元测试：backend=none 不改变排序，未知 backend 明确报错。
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
from libs.reranker.base_reranker import BaseReranker
from libs.reranker.none_reranker import NoneReranker
from libs.reranker.reranker_factory import create


def _make_settings(rerank_provider: str = "none") -> Settings:
    """构建用于测试的 Settings。"""
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


def test_backend_none_does_not_change_order() -> None:
    """provider=none 时返回 NoneReranker，不改变候选顺序。"""
    reranker = create(_make_settings(rerank_provider="none"))
    assert isinstance(reranker, NoneReranker)
    candidates = [
        {"id": "a", "score": 0.5},
        {"id": "b", "score": 0.9},
        {"id": "c", "score": 0.3},
    ]
    result = reranker.rerank("test query", candidates, trace=None)
    assert result == candidates
    assert [r["id"] for r in result] == ["a", "b", "c"]


def test_unknown_backend_raises() -> None:
    """未知 provider 时明确报错。"""
    with pytest.raises(ValueError) as exc_info:
        create(_make_settings(rerank_provider="unknown_reranker"))
    assert "unknown_reranker" in str(exc_info.value)
    assert "Unknown Reranker provider" in str(exc_info.value)


def test_none_reranker_preserves_list_identity() -> None:
    """NoneReranker 返回新列表，不修改原列表。"""
    reranker = NoneReranker(_make_settings())
    candidates = [{"id": "x", "score": 1.0}]
    result = reranker.rerank("q", candidates, trace=None)
    assert result is not candidates
    assert result == candidates


def test_none_reranker_empty_candidates_returns_empty_list() -> None:
    """空候选列表时 rerank 返回空列表，不抛异常。"""
    reranker = create(_make_settings(rerank_provider="none"))
    result = reranker.rerank("query", [], trace=None)
    assert result == []

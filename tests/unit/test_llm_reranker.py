"""
LLM Reranker 单元测试：mock LLM，验证工厂路由、结构化输出、schema 失败可读错误、失败回退。
"""

from typing import Any, Dict, List

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
from libs.reranker.llm_reranker import LLMReranker, _parse_ranked_ids
from libs.reranker.reranker_factory import create


def _make_settings(rerank_provider: str = "llm") -> Settings:
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


def test_factory_returns_llm_reranker_when_provider_llm() -> None:
    """provider=llm 时 RerankerFactory 可创建 LLMReranker。"""
    settings = _make_settings(rerank_provider="llm")
    reranker = create(settings)
    assert isinstance(reranker, LLMReranker)


def test_rerank_with_mock_llm_returns_ranked_order() -> None:
    """Mock LLM 返回合法 JSON 数组时，rerank 按该顺序重排。"""
    class MockLLM:
        def chat(self, messages: List[Dict[str, Any]]) -> str:
            return '["c", "a", "b"]'
    settings = _make_settings()
    reranker = LLMReranker(settings, prompt_text="{{query}}\n{{candidates}}", llm_client=MockLLM())
    candidates = [
        {"id": "a", "score": 0.5, "text": "A"},
        {"id": "b", "score": 0.9, "text": "B"},
        {"id": "c", "score": 0.3, "text": "C"},
    ]
    result = reranker.rerank("q", candidates, trace=None)
    assert [r["id"] for r in result] == ["c", "a", "b"]


def test_parse_ranked_ids_valid_json() -> None:
    """_parse_ranked_ids 解析合法 JSON 数组。"""
    assert _parse_ranked_ids('["x", "y"]') == ["x", "y"]
    assert _parse_ranked_ids('  ["a"]  ') == ["a"]


def test_parse_ranked_ids_invalid_schema_raises_readable() -> None:
    """输出非 JSON 数组或元素非 str 时抛出可读错误。"""
    with pytest.raises(ValueError) as exc_info:
        _parse_ranked_ids("not json")
    assert "LLM Reranker" in str(exc_info.value)
    with pytest.raises(ValueError) as exc_info:
        _parse_ranked_ids('{"key": "value"}')
    assert "数组" in str(exc_info.value)
    with pytest.raises(ValueError) as exc_info:
        _parse_ranked_ids("[1, 2]")
    assert "str" in str(exc_info.value)


def test_rerank_llm_exception_fallback_to_original_order() -> None:
    """LLM 抛出异常时回退为原序。"""
    class FailingLLM:
        def chat(self, messages: List[Dict[str, Any]]) -> str:
            raise RuntimeError("network error")
    settings = _make_settings()
    reranker = LLMReranker(settings, prompt_text="x", llm_client=FailingLLM())
    candidates = [{"id": "a", "score": 0.5}, {"id": "b", "score": 0.9}]
    result = reranker.rerank("q", candidates, trace=None)
    assert result == candidates


def test_rerank_empty_candidates_returns_empty() -> None:
    """空候选列表直接返回空列表，不调 LLM。"""
    class CalledLLM:
        def __init__(self):
            self.called = False
        def chat(self, messages: List[Dict[str, Any]]) -> str:
            self.called = True
            return "[]"
    mock = CalledLLM()
    settings = _make_settings()
    reranker = LLMReranker(settings, prompt_text="x", llm_client=mock)
    result = reranker.rerank("q", [], trace=None)
    assert result == []
    assert not mock.called

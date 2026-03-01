"""
LLM 工厂单元测试：用 Fake provider 验证工厂路由逻辑。
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
from libs.llm.base_llm import BaseLLM
from libs.llm.llm_factory import create, register_llm_provider


def _make_settings(llm_provider: str = "openai", llm_model: str = "gpt-4o-mini") -> Settings:
    """构建用于测试的 Settings（含指定 llm.provider）。"""
    return Settings(
        llm=LlmSettings(provider=llm_provider, model=llm_model),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class FakeLLM(BaseLLM):
    """测试用 Fake LLM，固定返回 stub 文本。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat(self, messages: List[Dict[str, Any]]) -> str:
        return "fake response"


def test_factory_returns_fake_when_registered() -> None:
    """注册 Fake provider 后，create(settings) 返回该实现实例。"""
    register_llm_provider("fake", FakeLLM)
    try:
        settings = _make_settings(llm_provider="fake")
        llm = create(settings)
        assert isinstance(llm, FakeLLM)
        assert llm.chat([{"role": "user", "content": "hi"}]) == "fake response"
    finally:
        # 从工厂中移除 fake，避免影响其他测试（若后续有真实 provider 注册）
        from libs.llm import llm_factory

        llm_factory._PROVIDERS.pop("fake", None)


def test_factory_unknown_provider_raises() -> None:
    """未知 provider 时抛出 ValueError，错误信息包含 provider 名称。"""
    settings = _make_settings(llm_provider="unknown_provider")
    with pytest.raises(ValueError) as exc_info:
        create(settings)
    assert "unknown_provider" in str(exc_info.value)
    assert "Unknown LLM provider" in str(exc_info.value)


def test_factory_routing_by_provider() -> None:
    """同一 settings 下不同 provider 路由到不同实现。"""
    class StubA(BaseLLM):
        def __init__(self, settings: Settings) -> None:
            pass
        def chat(self, messages: List[Dict[str, Any]]) -> str:
            return "A"

    class StubB(BaseLLM):
        def __init__(self, settings: Settings) -> None:
            pass
        def chat(self, messages: List[Dict[str, Any]]) -> str:
            return "B"

    register_llm_provider("stub_a", StubA)
    register_llm_provider("stub_b", StubB)
    try:
        sa = create(_make_settings(llm_provider="stub_a"))
        sb = create(_make_settings(llm_provider="stub_b"))
        assert sa.chat([]) == "A"
        assert sb.chat([]) == "B"
    finally:
        from libs.llm import llm_factory

        llm_factory._PROVIDERS.pop("stub_a", None)
        llm_factory._PROVIDERS.pop("stub_b", None)

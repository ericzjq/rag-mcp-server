"""
Splitter 工厂单元测试：Factory 能根据配置返回不同类型 Splitter（Fake 实现）。
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
from libs.splitter.base_splitter import BaseSplitter
from libs.splitter.splitter_factory import create, register_splitter_provider


def _make_settings(
    splitter_provider: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> Settings:
    """构建用于测试的 Settings（含指定 splitter.provider）。"""
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(
            provider=splitter_provider,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


class FakeSplitter(BaseSplitter):
    """测试用 Fake Splitter：按空格切分。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
    ) -> List[str]:
        return [s for s in text.split() if s]


def test_factory_returns_fake_when_registered() -> None:
    """注册 Fake provider 后，create(settings) 返回该实现实例。"""
    register_splitter_provider("fake", FakeSplitter)
    try:
        settings = _make_settings(splitter_provider="fake")
        splitter = create(settings)
        assert isinstance(splitter, FakeSplitter)
        assert splitter.split_text("a b c", trace=None) == ["a", "b", "c"]
    finally:
        from libs.splitter import splitter_factory

        splitter_factory._PROVIDERS.pop("fake", None)


def test_factory_unknown_provider_raises() -> None:
    """未知 provider 时抛出 ValueError，错误信息包含 provider 名称。"""
    settings = _make_settings(splitter_provider="unknown_splitter")
    with pytest.raises(ValueError) as exc_info:
        create(settings)
    assert "unknown_splitter" in str(exc_info.value)
    assert "Unknown Splitter provider" in str(exc_info.value)


def test_factory_routing_by_provider() -> None:
    """不同 provider 路由到不同实现。"""
    class StubA(BaseSplitter):
        def __init__(self, settings: Settings) -> None:
            pass
        def split_text(self, text: str, trace: Optional[Any] = None) -> List[str]:
            return ["A"]

    class StubB(BaseSplitter):
        def __init__(self, settings: Settings) -> None:
            pass
        def split_text(self, text: str, trace: Optional[Any] = None) -> List[str]:
            return ["B"]

    register_splitter_provider("stub_a", StubA)
    register_splitter_provider("stub_b", StubB)
    try:
        a = create(_make_settings(splitter_provider="stub_a"))
        b = create(_make_settings(splitter_provider="stub_b"))
        assert a.split_text("x") == ["A"]
        assert b.split_text("x") == ["B"]
    finally:
        from libs.splitter import splitter_factory

        splitter_factory._PROVIDERS.pop("stub_a", None)
        splitter_factory._PROVIDERS.pop("stub_b", None)

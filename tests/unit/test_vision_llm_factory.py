"""
Vision LLM 工厂单元测试：create_vision_llm 根据配置路由，Fake Vision LLM 验证接口。
"""

from typing import Any, Union

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
    VisionLlmSettings,
)
from libs.llm.base_vision_llm import BaseVisionLLM, ChatResponse
from libs.llm.deepseek_vision_llm import DeepSeekVisionLLM
from libs.llm.llm_factory import (
    LLMFactory,
    create_vision_llm,
    register_vision_llm_provider,
)


def _make_settings(
    vision_llm: VisionLlmSettings = None,
) -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
        vision_llm=vision_llm,
    )


class FakeVisionLLM(BaseVisionLLM):
    """测试用 Fake Vision LLM：返回固定内容。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat_with_image(
        self,
        text: str,
        image_path: Union[str, bytes],
        trace: Any = None,
    ) -> ChatResponse:
        return ChatResponse(content=f"caption:{text[:10]}")


def test_create_vision_llm_not_configured_raises() -> None:
    """vision_llm 未配置时 create_vision_llm 抛出 ValueError。"""
    settings = _make_settings(vision_llm=None)
    with pytest.raises(ValueError) as exc_info:
        create_vision_llm(settings)
    assert "vision_llm not configured" in str(exc_info.value)


def test_create_vision_llm_unknown_provider_raises() -> None:
    """vision_llm.provider 未注册时抛出 ValueError。"""
    settings = _make_settings(vision_llm=VisionLlmSettings(provider="unknown_vision"))
    with pytest.raises(ValueError) as exc_info:
        create_vision_llm(settings)
    assert "unknown_vision" in str(exc_info.value)


def test_create_vision_llm_deepseek_returns_deepseek_vision_llm() -> None:
    """provider=deepseek 且配置 base_url/model 时，create_vision_llm 返回 DeepSeekVisionLLM。"""
    settings = _make_settings(
        vision_llm=VisionLlmSettings(
            provider="deepseek",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        )
    )
    vision_llm = create_vision_llm(settings)
    assert isinstance(vision_llm, DeepSeekVisionLLM)


def test_factory_create_vision_llm_routes_to_fake() -> None:
    """注册 Fake 后，create_vision_llm(settings with provider=fake) 返回 FakeVisionLLM。"""
    register_vision_llm_provider("fake", FakeVisionLLM)
    try:
        settings = _make_settings(vision_llm=VisionLlmSettings(provider="fake"))
        vision_llm = create_vision_llm(settings)
        assert isinstance(vision_llm, FakeVisionLLM)
        resp = vision_llm.chat_with_image("describe this", "/path/to/img.png", trace=None)
        assert isinstance(resp, ChatResponse)
        assert resp.content == "caption:describe t"
    finally:
        from libs.llm import llm_factory
        llm_factory._VISION_PROVIDERS.pop("fake", None)


def test_llm_factory_create_vision_llm_method() -> None:
    """LLMFactory.create_vision_llm(settings) 与 create_vision_llm(settings) 一致。"""
    register_vision_llm_provider("fake2", FakeVisionLLM)
    try:
        settings = _make_settings(vision_llm=VisionLlmSettings(provider="fake2"))
        v1 = create_vision_llm(settings)
        v2 = LLMFactory.create_vision_llm(settings)
        assert type(v1) is type(v2)
        assert isinstance(v2, FakeVisionLLM)
    finally:
        from libs.llm import llm_factory
        llm_factory._VISION_PROVIDERS.pop("fake2", None)

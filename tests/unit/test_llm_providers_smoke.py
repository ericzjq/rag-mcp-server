"""
LLM 多 provider 烟雾测试：mock HTTP，不走真实网络。
验证工厂路由正确、chat 输入校验与异常信息可读（含 provider 与错误类型）。
"""

from typing import Any, Dict, List
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
from libs.llm.azure_llm import AzureLLM
from libs.llm.deepseek_llm import DeepSeekLLM
from libs.llm.llm_factory import create
from libs.llm.openai_llm import OpenAILLM


def _make_settings(
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    api_key: str = "test-key",
    base_url: str = "",
    azure_endpoint: str = "",
    api_version: str = "2024-02-15-preview",
) -> Settings:
    return Settings(
        llm=LlmSettings(
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
        ),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_routes_openai() -> None:
    """provider=openai 时工厂返回 OpenAILLM。"""
    settings = _make_settings(llm_provider="openai")
    llm = create(settings)
    assert isinstance(llm, OpenAILLM)


def test_factory_routes_azure() -> None:
    """provider=azure 时工厂返回 AzureLLM。"""
    settings = _make_settings(llm_provider="azure", azure_endpoint="https://x.openai.azure.com")
    llm = create(settings)
    assert isinstance(llm, AzureLLM)


def test_factory_routes_deepseek() -> None:
    """provider=deepseek 时工厂返回 DeepSeekLLM。"""
    settings = _make_settings(llm_provider="deepseek")
    llm = create(settings)
    assert isinstance(llm, DeepSeekLLM)


@patch("openai.OpenAI")
def test_openai_chat_mock_http(mock_openai_class: MagicMock) -> None:
    """OpenAI chat 使用 mock 客户端，不走真实网络。"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="hello"))],
    )
    mock_openai_class.return_value = mock_client

    settings = _make_settings(llm_provider="openai")
    llm = create(settings)
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert out == "hello"
    mock_client.chat.completions.create.assert_called_once()


def test_chat_empty_messages_raises_readable() -> None:
    """chat(messages=[]) 抛出可读错误，包含 provider 与错误类型。"""
    settings = _make_settings(llm_provider="openai")
    llm = create(settings)
    with pytest.raises(ValueError) as exc_info:
        llm.chat([])
    msg = str(exc_info.value)
    assert "openai" in msg.lower()
    assert "messages" in msg.lower()


def test_chat_invalid_messages_shape_raises_readable() -> None:
    """chat(messages=非 list) 抛出可读错误，含 provider。"""
    settings = _make_settings(llm_provider="azure")
    llm = create(settings)
    with pytest.raises(ValueError) as exc_info:
        llm.chat("not a list")  # type: ignore[arg-type]
    msg = str(exc_info.value)
    assert "azure" in msg.lower()

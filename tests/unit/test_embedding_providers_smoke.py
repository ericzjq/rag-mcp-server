"""
Embedding 多 provider 烟雾测试：mock HTTP，不走真实网络。
验证工厂路由 openai/azure、embed 输入校验、空输入报错含 provider。
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
from libs.embedding.azure_embedding import AzureEmbedding
from libs.embedding.embedding_factory import create
from libs.embedding.openai_embedding import OpenAIEmbedding


def _make_settings(
    embedding_provider: str = "openai",
    embedding_model: str = "text-embedding-3-small",
    api_key: str = "test-key",
    base_url: str = "",
    azure_endpoint: str = "",
    api_version: str = "2024-02-15-preview",
) -> Settings:
    return Settings(
        llm=LlmSettings(
            provider="openai",
            model="gpt-4o-mini",
            api_key="",
            base_url="",
            azure_endpoint="",
            api_version="2024-02-15-preview",
        ),
        embedding=EmbeddingSettings(
            provider=embedding_provider,
            model=embedding_model,
            api_key=api_key,
            base_url=base_url,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
        ),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_routes_openai() -> None:
    """provider=openai 时工厂返回 OpenAIEmbedding。"""
    settings = _make_settings(embedding_provider="openai")
    emb = create(settings)
    assert isinstance(emb, OpenAIEmbedding)


def test_factory_routes_azure() -> None:
    """provider=azure 时工厂返回 AzureEmbedding。"""
    settings = _make_settings(
        embedding_provider="azure",
        azure_endpoint="https://x.openai.azure.com",
    )
    emb = create(settings)
    assert isinstance(emb, AzureEmbedding)


@patch("openai.OpenAI")
def test_openai_embed_mock_http(mock_openai_class: MagicMock) -> None:
    """OpenAI embed 使用 mock 客户端，不走真实网络。"""
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[
            MagicMock(embedding=[0.1, 0.2, 0.3], index=0),
        ],
    )
    mock_openai_class.return_value = mock_client

    settings = _make_settings(embedding_provider="openai")
    emb = create(settings)
    out = emb.embed(["hello"], trace=None)
    assert out == [[0.1, 0.2, 0.3]]
    mock_client.embeddings.create.assert_called_once()
    call_kw = mock_client.embeddings.create.call_args[1]
    assert call_kw["model"] == "text-embedding-3-small"
    assert call_kw["input"] == ["hello"]


@patch("openai.AzureOpenAI")
def test_azure_embed_mock_http(mock_azure_class: MagicMock) -> None:
    """Azure embed 使用 mock 客户端，不走真实网络。"""
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[
            MagicMock(embedding=[0.5, 0.6, 0.7], index=0),
        ],
    )
    mock_azure_class.return_value = mock_client

    settings = _make_settings(
        embedding_provider="azure",
        embedding_model="text-embedding-ada-002",
        azure_endpoint="https://y.openai.azure.com",
    )
    emb = create(settings)
    out = emb.embed(["world"], trace=None)
    assert out == [[0.5, 0.6, 0.7]]
    mock_azure_class.assert_called_once()
    mock_client.embeddings.create.assert_called_once()
    assert mock_client.embeddings.create.call_args[1]["model"] == "text-embedding-ada-002"


def test_embed_empty_texts_raises_readable() -> None:
    """embed(texts=[]) 抛出可读错误，包含 provider。"""
    settings = _make_settings(embedding_provider="openai")
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed([], trace=None)
    msg = str(exc_info.value)
    assert "openai" in msg.lower()
    assert "texts" in msg.lower()


def test_embed_empty_texts_azure_raises_readable() -> None:
    """Azure embed(texts=[]) 抛出可读错误，包含 provider。"""
    settings = _make_settings(embedding_provider="azure", azure_endpoint="https://z.openai.azure.com")
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed([], trace=None)
    msg = str(exc_info.value)
    assert "azure" in msg.lower()
    assert "texts" in msg.lower()

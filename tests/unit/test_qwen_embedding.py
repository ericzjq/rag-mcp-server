"""
Qwen Embedding 单元测试：工厂路由、默认/自定义 base_url 与 model、
mock HTTP 正常响应、空输入报错、异常信息脱敏不泄露 api_key。
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
from libs.embedding.embedding_factory import create
from libs.embedding.qwen_embedding import DEFAULT_BASE_URL, DEFAULT_MODEL, QwenEmbedding


def _make_settings(
    embedding_provider: str = "qwen",
    embedding_model: str = "",
    api_key: str = "test-key",
    base_url: str = "",
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
            azure_endpoint="",
            api_version="2024-02-15-preview",
        ),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_returns_qwen_when_provider_qwen() -> None:
    """provider=qwen 时 EmbeddingFactory 可创建 QwenEmbedding。"""
    settings = _make_settings(embedding_provider="qwen")
    emb = create(settings)
    assert isinstance(emb, QwenEmbedding)


def test_qwen_uses_default_base_url_and_model_when_empty() -> None:
    """base_url 与 model 为空时使用默认 DashScope 地址与 text-embedding-v3。"""
    settings = _make_settings(base_url="", embedding_model="")
    emb = create(settings)
    assert emb._base_url == DEFAULT_BASE_URL
    assert emb._model == DEFAULT_MODEL


def test_qwen_uses_custom_base_url_and_model() -> None:
    """base_url 与 model 配置时使用配置值。"""
    settings = _make_settings(
        base_url="https://custom.dashscope.example/v1",
        embedding_model="text-embedding-v4",
    )
    emb = create(settings)
    assert emb._base_url == "https://custom.dashscope.example/v1"
    assert emb._model == "text-embedding-v4"


@patch("openai.OpenAI")
def test_qwen_embed_mock_http(mock_openai_class: MagicMock) -> None:
    """Qwen embed 使用 mock 客户端，不走真实网络；支持批量。"""
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[
            MagicMock(embedding=[0.1, 0.2, 0.3], index=0),
            MagicMock(embedding=[0.4, 0.5, 0.6], index=1),
        ],
    )
    mock_openai_class.return_value = mock_client

    settings = _make_settings()
    emb = create(settings)
    out = emb.embed(["a", "b"], trace=None)
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_client.embeddings.create.assert_called_once()
    call_kw = mock_client.embeddings.create.call_args[1]
    assert call_kw["model"] == DEFAULT_MODEL
    assert call_kw["input"] == ["a", "b"]


def test_qwen_embed_empty_texts_raises_readable() -> None:
    """embed(texts=[]) 抛出可读错误，包含 provider。"""
    settings = _make_settings()
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed([], trace=None)
    msg = str(exc_info.value)
    assert "qwen" in msg.lower()
    assert "texts" in msg.lower()


@patch("openai.OpenAI")
def test_qwen_exception_masks_api_key(mock_openai_class: MagicMock) -> None:
    """API 异常时错误信息不泄露 api_key。"""
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = Exception("Invalid API key: sk-secret123")
    mock_openai_class.return_value = mock_client

    settings = _make_settings(api_key="sk-secret123")
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed(["hi"], trace=None)
    msg = str(exc_info.value)
    assert "sk-secret123" not in msg
    assert "qwen" in msg.lower()

"""
Ollama Embedding 单元测试：工厂路由、默认/自定义 base_url、mock HTTP、
空输入报错、连接失败/超时可读错误且不泄露敏感配置。
"""

from unittest.mock import patch

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
from libs.embedding.ollama_embedding import OllamaEmbedding


def _make_settings(
    embedding_provider: str = "ollama",
    embedding_model: str = "nomic-embed-text",
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
            api_key="",
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


def test_factory_returns_ollama_when_provider_ollama() -> None:
    """provider=ollama 时 EmbeddingFactory 可创建 OllamaEmbedding。"""
    settings = _make_settings(embedding_provider="ollama")
    emb = create(settings)
    assert isinstance(emb, OllamaEmbedding)


def test_ollama_uses_default_base_url_when_empty() -> None:
    """base_url 为空时使用默认 http://localhost:11434。"""
    settings = _make_settings(base_url="")
    emb = create(settings)
    assert emb._base_url == "http://localhost:11434"


def test_ollama_uses_custom_base_url() -> None:
    """base_url 配置时使用配置值。"""
    settings = _make_settings(base_url="http://192.168.1.1:11434")
    emb = create(settings)
    assert emb._base_url == "http://192.168.1.1:11434"


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@patch("libs.embedding.ollama_embedding.urllib.request.urlopen")
def test_ollama_embed_mock_http(mock_urlopen: object) -> None:
    """Ollama embed 使用 mock HTTP，不走真实网络；支持批量。"""
    mock_urlopen.return_value = _FakeResponse(
        b'{"embeddings":[[0.1,0.2,0.3],[0.4,0.5,0.6]]}'
    )
    settings = _make_settings()
    emb = create(settings)
    out = emb.embed(["a", "b"], trace=None)
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_urlopen.assert_called_once()


def test_ollama_embed_empty_texts_raises_readable() -> None:
    """embed(texts=[]) 抛出可读错误，包含 provider。"""
    settings = _make_settings()
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed([], trace=None)
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "texts" in msg.lower()


@patch("libs.embedding.ollama_embedding.urllib.request.urlopen")
def test_ollama_connection_failure_raises_readable_no_leak(mock_urlopen: object) -> None:
    """连接失败时抛出可读错误且不泄露敏感配置。"""
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    settings = _make_settings(base_url="http://secret-host:11434")
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed(["hi"], trace=None)
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "secret-host" not in msg


@patch("libs.embedding.ollama_embedding.urllib.request.urlopen")
def test_ollama_timeout_raises_readable(mock_urlopen: object) -> None:
    """超时场景抛出可读错误。"""
    mock_urlopen.side_effect = TimeoutError("timed out")
    settings = _make_settings()
    emb = create(settings)
    with pytest.raises(ValueError) as exc_info:
        emb.embed(["hi"], trace=None)
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "超时" in msg or "timeout" in msg.lower()

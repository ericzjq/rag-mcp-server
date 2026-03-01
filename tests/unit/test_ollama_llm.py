"""
Ollama LLM 单元测试：工厂路由、mock HTTP 正常响应、连接失败/超时可读错误且不泄露敏感配置。
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
from libs.llm.llm_factory import create
from libs.llm.ollama_llm import OllamaLLM


def _make_settings(
    llm_provider: str = "ollama",
    llm_model: str = "llama3.2",
    base_url: str = "",
) -> Settings:
    return Settings(
        llm=LlmSettings(
            provider=llm_provider,
            model=llm_model,
            api_key="",
            base_url=base_url,
            azure_endpoint="",
            api_version="2024-02-15-preview",
        ),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_returns_ollama_when_provider_ollama() -> None:
    """provider=ollama 时可由 LLMFactory 创建 OllamaLLM。"""
    settings = _make_settings(llm_provider="ollama")
    llm = create(settings)
    assert isinstance(llm, OllamaLLM)


def test_ollama_uses_default_base_url_when_empty() -> None:
    """base_url 为空时使用默认 http://localhost:11434。"""
    settings = _make_settings(base_url="")
    llm = create(settings)
    assert llm._base_url == "http://localhost:11434"


def test_ollama_uses_custom_base_url() -> None:
    """base_url 配置时使用配置值。"""
    settings = _make_settings(base_url="http://192.168.1.1:11434")
    llm = create(settings)
    assert llm._base_url == "http://192.168.1.1:11434"


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@patch("libs.llm.ollama_llm.urllib.request.urlopen")
def test_ollama_chat_mock_http(mock_urlopen: object) -> None:
    """Ollama chat 使用 mock HTTP，不走真实网络。"""
    mock_urlopen.return_value = _FakeResponse(
        b'{"message":{"role":"assistant","content":"hello from ollama"},"done":true}'
    )
    settings = _make_settings()
    llm = create(settings)
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert out == "hello from ollama"
    mock_urlopen.assert_called_once()


def test_ollama_chat_empty_messages_raises_readable() -> None:
    """chat(messages=[]) 抛出可读错误，包含 provider。"""
    settings = _make_settings()
    llm = create(settings)
    with pytest.raises(ValueError) as exc_info:
        llm.chat([])
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "messages" in msg.lower()


@patch("libs.llm.ollama_llm.urllib.request.urlopen")
def test_ollama_connection_failure_raises_readable_no_leak(mock_urlopen: object) -> None:
    """连接失败时抛出可读错误且不泄露敏感配置。"""
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    settings = _make_settings(base_url="http://secret-host:11434")
    llm = create(settings)
    with pytest.raises(ValueError) as exc_info:
        llm.chat([{"role": "user", "content": "hi"}])
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "secret-host" not in msg
    assert "11434" not in msg or "localhost:11434" in msg  # 默认 URL 可接受


@patch("libs.llm.ollama_llm.urllib.request.urlopen")
def test_ollama_timeout_raises_readable(mock_urlopen: object) -> None:
    """超时场景抛出可读错误。"""
    mock_urlopen.side_effect = TimeoutError("timed out")
    settings = _make_settings()
    llm = create(settings)
    with pytest.raises(ValueError) as exc_info:
        llm.chat([{"role": "user", "content": "hi"}])
    msg = str(exc_info.value)
    assert "ollama" in msg.lower()
    assert "超时" in msg or "timeout" in msg.lower()

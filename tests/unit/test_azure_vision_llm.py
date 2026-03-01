"""
Azure Vision LLM 单元测试：mock HTTP，覆盖正常调用、图片路径/bytes、压缩、超时、认证失败。
"""

import io
import base64
from pathlib import Path
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
    VisionLlmSettings,
)
from libs.llm.azure_vision_llm import (
    AzureVisionLLM,
    _resize_image_if_needed,
    _load_image_bytes,
)
from libs.llm.base_vision_llm import ChatResponse
from libs.llm.llm_factory import create_vision_llm


def _make_settings(
    vision_llm: VisionLlmSettings,
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


def _vl_settings(
    provider: str = "azure",
    api_key: str = "test-key",
    azure_endpoint: str = "https://test.openai.azure.com",
    api_version: str = "2024-02-15-preview",
    deployment_name: str = "gpt-4o",
    max_image_size: int = 2048,
) -> VisionLlmSettings:
    return VisionLlmSettings(
        provider=provider,
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        api_version=api_version,
        deployment_name=deployment_name,
        max_image_size=max_image_size,
    )


def test_create_vision_llm_azure_returns_azure_vision_llm() -> None:
    """provider=azure 且配置 vision_llm 时，create_vision_llm 返回 AzureVisionLLM。"""
    settings = _make_settings(vision_llm=_vl_settings())
    vision_llm = create_vision_llm(settings)
    assert isinstance(vision_llm, AzureVisionLLM)


@patch("openai.AzureOpenAI")
def test_chat_with_image_success_returns_content(MockAzureOpenAI: MagicMock) -> None:
    """正常调用返回 ChatResponse，content 来自 API mock。"""
    mock_choice = MagicMock()
    mock_choice.message.content = "这是一张图片的描述"
    MockAzureOpenAI.return_value.chat.completions.create.return_value.choices = [mock_choice]

    settings = _make_settings(vision_llm=_vl_settings())
    model = AzureVisionLLM(settings)
    # 使用 base64 图片 bytes，避免真实文件
    png_header = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    resp = model.chat_with_image("describe", png_header, trace=None)

    assert isinstance(resp, ChatResponse)
    assert resp.content == "这是一张图片的描述"
    MockAzureOpenAI.return_value.chat.completions.create.assert_called_once()
    call_kw = MockAzureOpenAI.return_value.chat.completions.create.call_args[1]
    assert call_kw["model"] == "gpt-4o"
    messages = call_kw["messages"]
    assert len(messages) == 1 and messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert len(content) == 2
    assert content[0]["type"] == "text" and content[0]["text"] == "describe"
    assert content[1]["type"] == "image_url" and "base64," in content[1]["image_url"]["url"]


def test_chat_with_image_from_path(tmp_path: Path) -> None:
    """支持图片路径：写入临时文件后 chat_with_image(path) 可调用。"""
    png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    img_file = tmp_path / "img.png"
    img_file.write_bytes(png_bytes)

    with patch("openai.AzureOpenAI") as MockAzureOpenAI:
        mock_choice = MagicMock()
        mock_choice.message.content = "caption from path"
        MockAzureOpenAI.return_value.chat.completions.create.return_value.choices = [mock_choice]

        settings = _make_settings(vision_llm=_vl_settings())
        model = AzureVisionLLM(settings)
        resp = model.chat_with_image("what is this?", str(img_file), trace=None)

    assert resp.content == "caption from path"


def test_chat_with_image_file_not_found_raises() -> None:
    """图片路径不存在时抛出 ValueError（由 FileNotFoundError 转换）。"""
    settings = _make_settings(vision_llm=_vl_settings())
    model = AzureVisionLLM(settings)
    with pytest.raises(ValueError) as exc_info:
        model.chat_with_image("describe", "/nonexistent/image.png", trace=None)
    assert "不存在" in str(exc_info.value) or "nonexistent" in str(exc_info.value).lower()


def test_resize_image_if_needed_shrinks_large_image() -> None:
    """图片超过 max_size 时被缩小。"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")
    buf = io.BytesIO()
    img = Image.new("RGB", (3000, 2000), color="red")
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    out = _resize_image_if_needed(raw, 2048)
    resized = Image.open(io.BytesIO(out))
    assert max(resized.size) <= 2048


def test_resize_image_if_needed_small_image_unchanged() -> None:
    """图片未超过 max_size 时返回原 bytes。"""
    raw = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    out = _resize_image_if_needed(raw, 2048)
    assert out == raw


def test_load_image_bytes_from_path(tmp_path: Path) -> None:
    """_load_image_bytes(str) 从路径读取。"""
    f = tmp_path / "x.bin"
    f.write_bytes(b"\x00\x01\x02")
    assert _load_image_bytes(str(f)) == b"\x00\x01\x02"


def test_load_image_bytes_from_bytes() -> None:
    """_load_image_bytes(bytes) 原样返回。"""
    data = b"image data"
    assert _load_image_bytes(data) == data


@patch("openai.AzureOpenAI")
def test_chat_with_image_timeout_raises(MockAzureOpenAI: MagicMock) -> None:
    """API 超时时抛出包含错误的 ValueError。"""
    import socket
    MockAzureOpenAI.return_value.chat.completions.create.side_effect = socket.timeout("timed out")

    settings = _make_settings(vision_llm=_vl_settings())
    model = AzureVisionLLM(settings)
    png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    with pytest.raises(ValueError) as exc_info:
        model.chat_with_image("describe", png_bytes, trace=None)
    assert "azure" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


@patch("openai.AzureOpenAI")
def test_chat_with_image_auth_failure_raises_with_code(MockAzureOpenAI: MagicMock) -> None:
    """认证失败（如 401）时抛出 ValueError，错误信息含 code。"""
    err = Exception("Invalid API key")
    err.status_code = 401  # type: ignore[attr-defined]
    MockAzureOpenAI.return_value.chat.completions.create.side_effect = err

    settings = _make_settings(vision_llm=_vl_settings())
    model = AzureVisionLLM(settings)
    png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    with pytest.raises(ValueError) as exc_info:
        model.chat_with_image("describe", png_bytes, trace=None)
    assert "401" in str(exc_info.value) or "code" in str(exc_info.value).lower()

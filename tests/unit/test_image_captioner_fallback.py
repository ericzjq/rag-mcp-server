"""
ImageCaptioner 单元测试（C7）：启用模式 mock Vision LLM 写 caption；降级模式标记 has_unprocessed_images。
"""

from pathlib import Path
from typing import Any, Union
from unittest.mock import MagicMock

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
from core.types import Chunk
from ingestion.transform.image_captioner import (
    ImageCaptioner,
    _get_image_refs,
    _load_prompt,
)
from libs.llm.base_vision_llm import BaseVisionLLM, ChatResponse


def _make_settings(vision_llm=None) -> Settings:
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


def test_get_image_refs_empty() -> None:
    """无 images 或非列表时返回空。"""
    c = Chunk(id="c1", text="x", metadata={})
    assert _get_image_refs(c) == []
    c2 = Chunk(id="c2", text="x", metadata={"images": "not a list"})
    assert _get_image_refs(c2) == []


def test_get_image_refs_from_metadata() -> None:
    """从 metadata.images 取 id+path。"""
    c = Chunk(
        id="c1",
        text="x",
        metadata={
            "images": [
                {"id": "img1", "path": "/p/1.png"},
                {"id": "img2", "path": "/p/2.png"},
            ]
        },
    )
    refs = _get_image_refs(c)
    assert len(refs) == 2
    assert refs[0]["id"] == "img1" and refs[0]["path"] == "/p/1.png"


def test_load_prompt_returns_string() -> None:
    """_load_prompt 返回非空字符串。"""
    assert _load_prompt(Path("/nonexistent.txt"))
    assert isinstance(_load_prompt(None), str)


def test_chunk_without_images_passthrough() -> None:
    """无 image_refs 的 chunk 原样返回。"""
    settings = _make_settings(vision_llm=None)
    captioner = ImageCaptioner(settings)
    c = Chunk(id="c1", text="text", metadata={"source_path": "x"})
    out = captioner.transform([c], trace=None)
    assert len(out) == 1 and out[0].id == c.id and out[0].text == c.text
    assert "image_captions" not in out[0].metadata
    assert "has_unprocessed_images" not in out[0].metadata


def test_fallback_when_vision_llm_not_configured() -> None:
    """未配置 Vision LLM 时标记 has_unprocessed_images，不生成 caption。"""
    settings = _make_settings(vision_llm=None)
    captioner = ImageCaptioner(settings)
    c = Chunk(
        id="c1",
        text="x",
        metadata={"images": [{"id": "i1", "path": "/p/1.png"}]},
    )
    out = captioner.transform([c], trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("has_unprocessed_images") is True
    assert "image_captions" not in out[0].metadata or out[0].metadata.get("image_captions") == {}


def test_enabled_mode_mock_vision_llm_writes_caption(tmp_path: Path) -> None:
    """启用模式：mock Vision LLM 返回 caption，写入 metadata.image_captions。"""
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    mock_vision = MagicMock(spec=BaseVisionLLM)
    mock_vision.chat_with_image.return_value = ChatResponse(content="A diagram showing a flowchart.")

    settings = _make_settings(vision_llm=MagicMock())
    captioner = ImageCaptioner(settings, vision_llm_client=mock_vision)
    c = Chunk(
        id="c1",
        text="x",
        metadata={"images": [{"id": "i1", "path": str(img_path)}]},
    )
    out = captioner.transform([c], trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("image_captions", {}).get("i1") == "A diagram showing a flowchart."
    mock_vision.chat_with_image.assert_called_once()


def test_fallback_on_vision_llm_exception(tmp_path: Path) -> None:
    """Vision LLM 抛异常时标记 has_unprocessed_images，不阻塞。"""
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"\x00")
    mock_vision = MagicMock(spec=BaseVisionLLM)
    mock_vision.chat_with_image.side_effect = RuntimeError("api error")

    settings = _make_settings(vision_llm=MagicMock())
    captioner = ImageCaptioner(settings, vision_llm_client=mock_vision)
    c = Chunk(
        id="c1",
        text="x",
        metadata={"images": [{"id": "i1", "path": str(img_path)}]},
    )
    out = captioner.transform([c], trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("has_unprocessed_images") is True

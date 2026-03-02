"""
MultimodalAssembler 单元测试（E6）：image_refs 转为 ImageContent，mimeType、base64。
"""

import base64
from pathlib import Path

import pytest

from core.types import RetrievalResult
from core.response.multimodal_assembler import assemble


def test_assemble_empty_results_returns_empty_list() -> None:
    assert assemble([]) == []


def test_assemble_no_image_refs_returns_empty_list() -> None:
    results = [RetrievalResult("c1", 0.9, "text", {})]
    assert assemble(results) == []


def test_assemble_returns_image_content_with_mime_and_base64(tmp_path: Path) -> None:
    """命中 chunk 含 image_refs 时返回 content 含 image type、mimeType、base64。"""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    img_dir = tmp_path / "data" / "images" / "coll"
    img_dir.mkdir(parents=True)
    img_path = img_dir / "x.png"
    img_path.write_bytes(png_bytes)

    results = [
        RetrievalResult(
            "c1",
            0.9,
            "Text.",
            {"images": [{"id": "i1", "path": str(img_path)}]},
        ),
    ]
    out = assemble(results, work_dir=str(tmp_path))

    assert len(out) == 1
    assert out[0]["type"] == "image"
    assert out[0]["mimeType"] == "image/png"
    assert isinstance(out[0]["data"], str)
    assert len(out[0]["data"]) > 0
    assert base64.b64decode(out[0]["data"]) == png_bytes


def test_assemble_relative_path_resolved_against_work_dir(tmp_path: Path) -> None:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "a.jpg").write_bytes(png_bytes)

    results = [
        RetrievalResult("c1", 0.9, "x", {"images": [{"id": "i1", "path": "img/a.jpg"}]}),
    ]
    out = assemble(results, work_dir=str(tmp_path))

    assert len(out) == 1
    assert out[0]["mimeType"] == "image/jpeg"


def test_assemble_skips_missing_file() -> None:
    results = [
        RetrievalResult(
            "c1",
            0.9,
            "x",
            {"images": [{"id": "i1", "path": "nonexistent.png"}]},
        ),
    ]
    out = assemble(results, work_dir="/tmp")
    assert len(out) == 0

"""
get_document_summary 单元测试（E5）：不存在返回规范错误，存在时返回结构化信息。
"""

import json
import tempfile
from pathlib import Path

import pytest

from mcp_server.tools.get_document_summary import get_document_summary


def test_get_document_summary_not_found_returns_structured_error() -> None:
    """不存在 doc_id 时返回规范错误（structuredContent.error=not_found）。"""
    result = get_document_summary("nonexistent", _store={})

    assert result["structuredContent"].get("error") == "not_found"
    assert result["structuredContent"].get("doc_id") == "nonexistent"
    assert "文档不存在" in result["content"][0]["text"]


def test_get_document_summary_found_returns_title_summary_tags() -> None:
    """存在时返回 title、summary、tags。"""
    store = {
        "doc_1": {
            "title": "Test Doc",
            "summary": "A short summary.",
            "tags": ["a", "b"],
        },
    }
    result = get_document_summary("doc_1", _store=store)

    assert "error" not in result["structuredContent"]
    assert result["structuredContent"]["doc_id"] == "doc_1"
    assert result["structuredContent"]["title"] == "Test Doc"
    assert result["structuredContent"]["summary"] == "A short summary."
    assert result["structuredContent"]["tags"] == ["a", "b"]
    assert result["content"][0]["type"] == "text"
    assert "Test Doc" in result["content"][0]["text"]
    assert "A short summary" in result["content"][0]["text"]


def test_get_document_summary_from_file(tmp_path: Path) -> None:
    """从 metadata 文件读取时，存在则返回，不存在则 not_found。"""
    meta_file = tmp_path / "doc_meta.json"
    meta_file.write_text(
        json.dumps({"known_id": {"title": "T", "summary": "S", "tags": []}}, ensure_ascii=False),
        encoding="utf-8",
    )

    found = get_document_summary("known_id", metadata_path=str(meta_file), work_dir=str(tmp_path))
    assert found["structuredContent"].get("title") == "T"

    not_found = get_document_summary("other_id", metadata_path=str(meta_file), work_dir=str(tmp_path))
    assert not_found["structuredContent"].get("error") == "not_found"


def test_get_document_summary_missing_file_returns_not_found() -> None:
    """metadata 文件不存在时视为 not_found。"""
    result = get_document_summary("any", metadata_path="nonexistent.json", work_dir="/tmp")
    assert result["structuredContent"].get("error") == "not_found"

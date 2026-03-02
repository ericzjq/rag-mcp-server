"""
list_collections 单元测试（E4）：对 fixtures 目录结构返回集合名列表。
"""

from pathlib import Path

import pytest

from mcp_server.tools.list_collections import list_collections


def test_list_collections_returns_subdir_names(tmp_path: Path) -> None:
    """data/documents 下存在子目录时返回集合名列表（排序）。"""
    doc_root = tmp_path / "data" / "documents"
    doc_root.mkdir(parents=True)
    (doc_root / "foo").mkdir()
    (doc_root / "bar").mkdir()
    (doc_root / "baz").mkdir()

    result = list_collections(documents_base="data/documents", work_dir=str(tmp_path))

    assert "structuredContent" in result
    assert result["structuredContent"]["collections"] == ["bar", "baz", "foo"]
    assert result["content"][0]["type"] == "text"
    assert "foo" in result["content"][0]["text"]
    assert "bar" in result["content"][0]["text"]


def test_list_collections_empty_dir_returns_empty_list(tmp_path: Path) -> None:
    """空目录返回空列表与友好文案。"""
    doc_root = tmp_path / "data" / "documents"
    doc_root.mkdir(parents=True)

    result = list_collections(documents_base="data/documents", work_dir=str(tmp_path))

    assert result["structuredContent"]["collections"] == []
    assert "无文档集合" in result["content"][0]["text"] or "无" in result["content"][0]["text"]


def test_list_collections_missing_dir_returns_empty_list(tmp_path: Path) -> None:
    """目录不存在时返回空列表。"""
    result = list_collections(documents_base="data/documents", work_dir=str(tmp_path))

    assert result["structuredContent"]["collections"] == []


def test_list_collections_ignores_dot_dirs(tmp_path: Path) -> None:
    """以点开头的子目录不列入集合。"""
    doc_root = tmp_path / "docs"
    doc_root.mkdir()
    (doc_root / "public").mkdir()
    (doc_root / ".hidden").mkdir()

    result = list_collections(documents_base="docs", work_dir=str(tmp_path))

    assert result["structuredContent"]["collections"] == ["public"]

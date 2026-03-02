"""
ResponseBuilder 单元测试（E3）：Markdown 引用、citations、无结果友好提示。
"""

import pytest

from core.types import RetrievalResult
from core.response.response_builder import build
from core.response.citation_generator import generate


def test_build_empty_results_friendly_message() -> None:
    out = build([], "any query")
    assert out["content"][0]["type"] == "text"
    assert "未找到" in out["content"][0]["text"]
    assert out["structuredContent"]["citations"] == []


def test_build_single_result_markdown_and_citation() -> None:
    results = [
        RetrievalResult(
            chunk_id="c1",
            score=0.9,
            text="Some relevant text.",
            metadata={"source_path": "/doc.pdf", "page": 1},
        ),
    ]
    out = build(results, "q")
    assert out["content"][0]["type"] == "text"
    assert "[1]" in out["content"][0]["text"]
    assert "Some relevant text" in out["content"][0]["text"]
    assert len(out["structuredContent"]["citations"]) == 1
    assert out["structuredContent"]["citations"][0]["source"] == "/doc.pdf"
    assert out["structuredContent"]["citations"][0]["page"] == 1
    assert out["structuredContent"]["citations"][0]["chunk_id"] == "c1"
    assert out["structuredContent"]["citations"][0]["score"] == 0.9


def test_build_multiple_results_numbered_refs() -> None:
    results = [
        RetrievalResult("c1", 0.9, "First.", {}),
        RetrievalResult("c2", 0.8, "Second.", {}),
    ]
    out = build(results, "q")
    assert "[1]" in out["content"][0]["text"]
    assert "[2]" in out["content"][0]["text"]
    assert "First" in out["content"][0]["text"]
    assert "Second" in out["content"][0]["text"]
    assert len(out["structuredContent"]["citations"]) == 2


def test_generate_citations_source_page_chunk_id_score() -> None:
    results = [
        RetrievalResult("chunk-a", 0.85, "x", {"source_path": "a.pdf", "page_num": 2}),
    ]
    citations = generate(results)
    assert citations[0]["source"] == "a.pdf"
    assert citations[0]["page"] == 2
    assert citations[0]["chunk_id"] == "chunk-a"
    assert citations[0]["score"] == 0.85

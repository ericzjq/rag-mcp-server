"""
ChunkRefiner 单元测试（C5）：规则去噪、保留干净/代码块、mock LLM、降级、单条异常不阻塞。
"""

import json
from pathlib import Path
from typing import Any, List
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
from ingestion.transform.chunk_refiner import (
    ChunkRefiner,
    _load_prompt,
    _rule_based_refine,
)


def _make_settings() -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def _chunk(text: str, id: str = "c1") -> Chunk:
    return Chunk(id=id, text=text, metadata={"source_path": "x"}, source_ref="doc1")


# --- rule-based ---


def test_rule_based_refine_excessive_whitespace() -> None:
    """规则：连续空白归一。"""
    out = _rule_based_refine("a\n\n\n\nb\t\t  c")
    assert "a" in out and "b" in out and "c" in out
    assert "\n\n\n\n" not in out


def test_rule_based_refine_page_header_footer() -> None:
    """规则：页眉页脚模式去除。"""
    out = _rule_based_refine("— 1 —\nPage 1\n\nContent\n\n1/5")
    assert "Content" in out
    assert "— 1 —" not in out or "Page 1" not in out


def test_rule_based_refine_html_comment_removed() -> None:
    """规则：HTML 注释去除。"""
    out = _rule_based_refine("before <!-- comment --> after")
    assert "before" in out and "after" in out
    assert "comment" not in out


def test_rule_based_refine_clean_text_unchanged() -> None:
    """干净文本不过度清理。"""
    text = "This is already clean."
    assert _rule_based_refine(text) == text


def test_rule_based_refine_preserves_code_block() -> None:
    """代码块内部格式保留。"""
    text = "```python\ndef foo():\n    return 1\n```"
    out = _rule_based_refine(text)
    assert "def foo():" in out and "return 1" in out


def test_rule_based_refine_fixtures() -> None:
    """对 noisy_chunks.json 中样例能去噪。"""
    fixtures_path = Path(__file__).resolve().parent.parent / "fixtures" / "noisy_chunks.json"
    if not fixtures_path.exists():
        pytest.skip("noisy_chunks.json not found")
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))
    for key, raw in data.items():
        out = _rule_based_refine(raw)
        assert isinstance(out, str)
        if key == "clean_text":
            assert "clean" in out.lower() or "already" in out.lower()


# --- prompt ---


def test_load_prompt_contains_text_placeholder() -> None:
    """_load_prompt 返回含 {text} 的模板。"""
    t = _load_prompt(Path("/nonexistent/path.txt"))
    assert "{text}" in t


# --- transform ---


def test_transform_rule_only_marks_refined_by_rule() -> None:
    """use_llm=False 时全部为 refined_by: rule。"""
    refiner = ChunkRefiner(_make_settings(), use_llm=False)
    chunks = [_chunk("noise   here", "c1")]
    out = refiner.transform(chunks, trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("refined_by") == "rule"
    assert "noise" in out[0].text and "here" in out[0].text


def test_transform_with_mock_llm_marks_refined_by_llm() -> None:
    """Mock LLM 返回时 refined_by: llm。"""
    mock_llm = MagicMock()
    mock_llm.chat.return_value = "refined content"
    refiner = ChunkRefiner(_make_settings(), use_llm=True, llm_client=mock_llm)
    chunks = [_chunk("original", "c1")]
    out = refiner.transform(chunks, trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("refined_by") == "llm"
    assert out[0].text == "refined content"


def test_transform_llm_failure_fallback_to_rule() -> None:
    """LLM 抛异常时回退规则结果，metadata 含 refinement_fallback。"""
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = RuntimeError("api error")
    refiner = ChunkRefiner(_make_settings(), use_llm=True, llm_client=mock_llm)
    chunks = [_chunk("  text  ", "c1")]
    out = refiner.transform(chunks, trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("refined_by") == "rule"
    assert out[0].metadata.get("refinement_fallback") == "llm_failed"
    assert "text" in out[0].text


def test_transform_single_chunk_exception_keeps_others() -> None:
    """单条处理异常时保留原文并标记，其余正常。"""
    from unittest.mock import patch
    call_count = [0]
    def rule_raise_second(text):
        call_count[0] += 1
        if call_count[0] == 2:
            raise ValueError("simulated")
        return _rule_based_refine(text)
    refiner = ChunkRefiner(_make_settings(), use_llm=False)
    c1 = _chunk("first", "c1")
    c2 = _chunk("second", "c2")
    with patch("ingestion.transform.chunk_refiner._rule_based_refine", side_effect=rule_raise_second):
        out = refiner.transform([c1, c2], trace=None)
    assert len(out) == 2
    assert out[0].metadata.get("refined_by") == "rule" and "first" in out[0].text
    assert out[1].text == "second" and out[1].metadata.get("refined_by") == "rule"
    assert "refinement_fallback" in out[1].metadata


def test_transform_preserves_chunk_id_and_source_ref() -> None:
    """transform 保留 id、source_ref。"""
    refiner = ChunkRefiner(_make_settings(), use_llm=False)
    c = _chunk("x", id="chunk_001")
    c = Chunk(id="chunk_001", text="x", metadata={}, source_ref="doc99")
    out = refiner.transform([c], trace=None)
    assert out[0].id == "chunk_001" and out[0].source_ref == "doc99"


def test_transform_empty_list_returns_empty() -> None:
    """空列表入则空列表出。"""
    refiner = ChunkRefiner(_make_settings(), use_llm=False)
    assert refiner.transform([], trace=None) == []

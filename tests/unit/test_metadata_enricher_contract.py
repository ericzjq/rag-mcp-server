"""
MetadataEnricher 契约测试（C6）：规则模式 title/summary/tags 非空；LLM mock 增强；降级行为。
"""

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
from ingestion.transform.metadata_enricher import (
    MetadataEnricher,
    _rule_title,
    _rule_summary,
    _rule_tags,
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


def test_rule_mode_output_has_title_summary_tags() -> None:
    """规则模式：输出 metadata 必须包含 title、summary、tags（至少非空）。"""
    enricher = MetadataEnricher(_make_settings(), use_llm=False)
    chunks = [_chunk("First line.\n\nMore content here.")]
    out = enricher.transform(chunks, trace=None)
    assert len(out) == 1
    m = out[0].metadata
    assert "title" in m and m["title"]
    assert "summary" in m and m["summary"]
    assert "tags" in m and isinstance(m["tags"], list)
    assert m.get("enriched_by") == "rule"


def test_rule_title_first_line() -> None:
    """_rule_title 取首行。"""
    assert "First" in _rule_title("First line.\nSecond.")
    assert _rule_title("") == "(no title)"


def test_rule_summary_truncated() -> None:
    """_rule_summary 截断。"""
    s = _rule_summary("a" * 300)
    assert len(s) <= 201
    assert "…" in s or len(s) == 200


def test_rule_tags_hashtag_or_fallback() -> None:
    """_rule_tags 可提取 #tag 或兜底。"""
    assert "chunk" in _rule_tags("no hashtags")
    t = _rule_tags("#python #code")
    assert "python" in t or "code" in t


def test_llm_mode_enriches_metadata() -> None:
    """LLM 模式（mock）：生成 title/summary/tags，enriched_by: llm。"""
    mock_llm = MagicMock()
    mock_llm.chat.return_value = '{"title": "My Title", "summary": "A summary.", "tags": ["a", "b"]}'
    enricher = MetadataEnricher(_make_settings(), use_llm=True, llm_client=mock_llm)
    chunks = [_chunk("Some text.")]
    out = enricher.transform(chunks, trace=None)
    assert len(out) == 1
    m = out[0].metadata
    assert m.get("enriched_by") == "llm"
    assert m.get("title") == "My Title"
    assert m.get("summary") == "A summary."
    assert m.get("tags") == ["a", "b"]


def test_llm_failure_fallback_to_rule() -> None:
    """LLM 调用失败时回退到规则结果，标记 enrichment_fallback。"""
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = RuntimeError("api error")
    enricher = MetadataEnricher(_make_settings(), use_llm=True, llm_client=mock_llm)
    chunks = [_chunk("Hello world.")]
    out = enricher.transform(chunks, trace=None)
    assert len(out) == 1
    m = out[0].metadata
    assert m.get("enriched_by") == "rule"
    assert m.get("enrichment_fallback") == "llm_failed"
    assert m.get("title") and m.get("summary") and m.get("tags") is not None


def test_transform_preserves_chunk_id_and_text() -> None:
    """transform 不修改 id、text、source_ref。"""
    enricher = MetadataEnricher(_make_settings(), use_llm=False)
    c = _chunk("Content.", id="chunk_42")
    c = Chunk(id="chunk_42", text="Content.", metadata={}, source_ref="doc99")
    out = enricher.transform([c], trace=None)
    assert out[0].id == "chunk_42" and out[0].text == "Content." and out[0].source_ref == "doc99"


def test_transform_empty_list() -> None:
    """空列表入则空列表出。"""
    enricher = MetadataEnricher(_make_settings(), use_llm=False)
    assert enricher.transform([], trace=None) == []

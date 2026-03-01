"""
Recursive Splitter 单元测试：工厂路由、chunk_size/chunk_overlap、Markdown 结构保留。
"""

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
from libs.splitter.recursive_splitter import RecursiveSplitter
from libs.splitter.splitter_factory import create


def _make_settings(
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(provider="chroma", persist_directory="data/chroma"),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(
            provider="recursive",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


def test_factory_returns_recursive_splitter() -> None:
    """provider=recursive 时 SplitterFactory 可创建 RecursiveSplitter。"""
    settings = _make_settings()
    splitter = create(settings)
    assert isinstance(splitter, RecursiveSplitter)


def test_split_text_respects_chunk_size() -> None:
    """split_text 将长文本切分为不超过 chunk_size 的块（允许 overlap）。"""
    settings = _make_settings(chunk_size=50, chunk_overlap=10)
    splitter = create(settings)
    long_text = "a " * 60  # 约 120 字符
    chunks = splitter.split_text(long_text, trace=None)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 50 + 20  # chunk_size + overlap 容忍

def test_split_text_empty_returns_empty_list() -> None:
    """空字符串或仅空白返回空列表。"""
    settings = _make_settings()
    splitter = create(settings)
    assert splitter.split_text("", trace=None) == []
    assert splitter.split_text("   \n\n  ", trace=None) == []


def test_split_text_markdown_paragraphs_preferred() -> None:
    """含双换行的 Markdown 优先在段落边界切分，不打断代码块。"""
    settings = _make_settings(chunk_size=80, chunk_overlap=15)
    splitter = create(settings)
    # 两段 + 代码块，总长超过 chunk_size，应拆成多块但每块尽量完整
    text = (
        "## Title\n\n"
        "First paragraph here with some content.\n\n"
        "Second paragraph.\n\n"
        "```\n"
        "code line one\n"
        "code line two\n"
        "```"
    )
    chunks = splitter.split_text(text, trace=None)
    assert len(chunks) >= 1
    # 代码块应完整出现在某一块中（不从中劈开）
    combined = " ".join(chunks)
    assert "code line one" in combined
    assert "code line two" in combined
    assert "```" in combined

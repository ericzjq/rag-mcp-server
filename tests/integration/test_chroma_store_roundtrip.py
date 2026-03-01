"""
ChromaStore 集成测试：upsert → query 完整往返，使用临时目录，测试结束后清理。
依赖 chromadb（见 pyproject.toml）；未安装时请 pip install chromadb 后运行。
"""

import tempfile

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
from libs.vector_store.chroma_store import ChromaStore
from libs.vector_store.vector_store_factory import create


def _make_settings(persist_directory: str) -> Settings:
    return Settings(
        llm=LlmSettings(provider="openai", model="gpt-4o-mini"),
        embedding=EmbeddingSettings(provider="openai", model="text-embedding-3-small"),
        vector_store=VectorStoreSettings(
            provider="chroma",
            persist_directory=persist_directory,
        ),
        retrieval=RetrievalSettings(top_k=10, rerank_top_m=20),
        rerank=RerankSettings(provider="none"),
        splitter=SplitterSettings(provider="recursive", chunk_size=512, chunk_overlap=50),
        evaluation=EvaluationSettings(provider="ragas"),
        observability=ObservabilitySettings(log_level="INFO", traces_path="logs/traces.jsonl"),
    )


@pytest.mark.integration
def test_chroma_upsert_query_roundtrip() -> None:
    """upsert 后 query 能按向量相似度返回正确 Top-K，结果含 id、score、text。"""
    with tempfile.TemporaryDirectory() as tmp:
        settings = _make_settings(tmp)
        store = create(settings)
        assert isinstance(store, ChromaStore)

        # 三条记录，向量故意区分：v1 与 v1 相似度最高，与 v2 次之，与 v3 最低
        records = [
            {"id": "chunk-1", "vector": [1.0, 0.0, 0.0], "metadata": {"source": "doc1", "text": "First chunk."}},
            {"id": "chunk-2", "vector": [0.9, 0.1, 0.0], "metadata": {"source": "doc1", "text": "Second chunk."}},
            {"id": "chunk-3", "vector": [0.0, 0.0, 1.0], "metadata": {"source": "doc2", "text": "Third chunk."}},
        ]
        store.upsert(records, trace=None)

        # 用与 chunk-1 相同的向量查询，top_k=2，应返回 chunk-1 和 chunk-2（且 chunk-1 分数最高）
        results = store.query([1.0, 0.0, 0.0], top_k=2, filters=None, trace=None)
        assert len(results) == 2
        ids = [r["id"] for r in results]
        assert "chunk-1" in ids
        assert "chunk-2" in ids
        assert results[0]["score"] >= results[1]["score"]
        assert results[0]["id"] == "chunk-1"
        # 返回应含 text
        assert "text" in results[0]
        assert results[0]["text"] == "First chunk."


@pytest.mark.integration
def test_chroma_query_top_k() -> None:
    """query 的 top_k 参数限制返回条数。"""
    with tempfile.TemporaryDirectory() as tmp:
        settings = _make_settings(tmp)
        store = create(settings)
        records = [
            {"id": "a", "vector": [1.0, 0.0], "metadata": {"text": "A"}},
            {"id": "b", "vector": [0.99, 0.01], "metadata": {"text": "B"}},
            {"id": "c", "vector": [0.98, 0.02], "metadata": {"text": "C"}},
        ]
        store.upsert(records, trace=None)
        results = store.query([1.0, 0.0], top_k=2, filters=None, trace=None)
        assert len(results) == 2
        results5 = store.query([1.0, 0.0], top_k=5, filters=None, trace=None)
        assert len(results5) == 3  # 只有 3 条


@pytest.mark.integration
def test_chroma_query_with_metadata_filter() -> None:
    """query 支持 metadata filters（如 source），只返回匹配记录。"""
    with tempfile.TemporaryDirectory() as tmp:
        settings = _make_settings(tmp)
        store = create(settings)
        records = [
            {"id": "x1", "vector": [1.0, 0.0], "metadata": {"source": "docA", "text": "From A"}},
            {"id": "x2", "vector": [0.99, 0.0], "metadata": {"source": "docB", "text": "From B"}},
        ]
        store.upsert(records, trace=None)
        results = store.query([1.0, 0.0], top_k=10, filters={"source": "docA"}, trace=None)
        assert len(results) >= 1
        assert all(r.get("metadata", {}).get("source") == "docA" for r in results)

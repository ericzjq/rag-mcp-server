"""
Reranker 单元测试（D6）：模拟后端异常时不影响最终返回，且标记 fallback=true。
"""

from typing import Any, List, Optional

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
from core.types import RetrievalResult
from core.query_engine.reranker import Reranker
from libs.reranker.base_reranker import BaseReranker, RerankCandidate


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


def _result(cid: str, score: float = 0.5, text: str = "", metadata: dict = None) -> RetrievalResult:
    return RetrievalResult(chunk_id=cid, score=score, text=text or cid, metadata=metadata or {})


class _FailingReranker(BaseReranker):
    """始终抛异常的后端。"""

    def rerank(
        self,
        query: str,
        candidates: List[RerankCandidate],
        trace: Optional[Any] = None,
    ) -> List[RerankCandidate]:
        raise RuntimeError("reranker backend failed")


def test_reranker_fallback_on_backend_exception() -> None:
    """后端异常时返回原候选且标记 rerank_fallback=True。"""
    reranker = Reranker(_make_settings(), backend=_FailingReranker())
    candidates = [
        _result("c1", 0.9, "A"),
        _result("c2", 0.7, "B"),
    ]
    out = reranker.rerank("query", candidates, trace=None)
    assert len(out) == 2
    assert out[0].chunk_id == "c1" and out[1].chunk_id == "c2"
    assert out[0].text == "A" and out[1].text == "B"
    assert out[0].metadata.get("rerank_fallback") is True
    assert out[1].metadata.get("rerank_fallback") is True


def test_reranker_success_no_fallback() -> None:
    """后端正常时返回重排结果且无 fallback 标记。"""
    class _IdentityReranker(BaseReranker):
        def rerank(self, query: str, candidates: List[RerankCandidate], trace: Optional[Any] = None) -> List[RerankCandidate]:
            return list(candidates)
    reranker = Reranker(_make_settings(), backend=_IdentityReranker())
    candidates = [_result("x", 0.5, "X")]
    out = reranker.rerank("q", candidates, trace=None)
    assert len(out) == 1 and out[0].chunk_id == "x"
    assert out[0].metadata.get("rerank_fallback") is not True


def test_reranker_empty_candidates() -> None:
    """空候选返回空列表。"""
    reranker = Reranker(_make_settings(), backend=_FailingReranker())
    assert reranker.rerank("q", [], trace=None) == []

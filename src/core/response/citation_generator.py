"""
CitationGenerator（E3）：从 RetrievalResult 列表生成结构化引用列表。
"""

from typing import Any, Dict, List

from core.types import RetrievalResult


def generate(retrieval_results: List[RetrievalResult]) -> List[Dict[str, Any]]:
    """生成引用列表，每项含 source、page、chunk_id、score。"""
    citations = []
    for r in retrieval_results:
        citations.append({
            "source": r.metadata.get("source_path", ""),
            "page": r.metadata.get("page", r.metadata.get("page_num", "")),
            "chunk_id": r.chunk_id,
            "score": round(r.score, 4),
        })
    return citations

"""
Fusion（D4）：RRF (Reciprocal Rank Fusion) 融合多路排名，输出统一排序。
"""

from typing import List

from core.types import RetrievalResult

# RRF 常用默认 k（抑制高位排名差异）
DEFAULT_RRF_K = 60


def rrf_fuse(
    ranked_lists: List[List[RetrievalResult]],
    k: int = DEFAULT_RRF_K,
) -> List[RetrievalResult]:
    """
    对多路检索结果做 RRF 融合：score(d) = sum_i 1/(k + rank_i(d))，按融合分降序、chunk_id 升序稳定排序。

    Args:
        ranked_lists: 多路结果列表，每路为按排名顺序的 RetrievalResult 列表。
        k: RRF 常数，默认 60。

    Returns:
        去重后的 RetrievalResult 列表（按 RRF 分降序，同分按 chunk_id 升序），每条保留首次出现的 text/metadata。
    """
    if not ranked_lists:
        return []
    k = max(1, int(k))
    rrf_scores: dict[str, float] = {}
    first_seen: dict[str, RetrievalResult] = {}
    for rank_list in ranked_lists:
        for i, item in enumerate(rank_list):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + i + 1)
            if cid not in first_seen:
                first_seen[cid] = item
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: (-rrf_scores[x], x))
    return [
        RetrievalResult(
            chunk_id=cid,
            score=rrf_scores[cid],
            text=first_seen[cid].text,
            metadata=dict(first_seen[cid].metadata),
        )
        for cid in sorted_ids
    ]

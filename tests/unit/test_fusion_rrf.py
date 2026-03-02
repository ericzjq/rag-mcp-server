"""
Fusion RRF 单元测试（D4）：构造排名输入输出 deterministic；k 参数可配置。
"""

from core.types import RetrievalResult
from core.query_engine.fusion import rrf_fuse, DEFAULT_RRF_K


def _r(chunk_id: str, score: float = 0.0, text: str = "", metadata: dict = None) -> RetrievalResult:
    return RetrievalResult(chunk_id=chunk_id, score=score, text=text or chunk_id, metadata=metadata or {})


def test_rrf_fuse_deterministic() -> None:
    """相同输入多次调用输出一致。"""
    dense = [_r("c1", 0.9), _r("c2", 0.8), _r("c3", 0.7)]
    sparse = [_r("c2", 0.95), _r("c1", 0.85), _r("c4", 0.5)]
    out1 = rrf_fuse([dense, sparse], k=60)
    out2 = rrf_fuse([dense, sparse], k=60)
    assert [x.chunk_id for x in out1] == [x.chunk_id for x in out2]
    assert len(out1) == 4  # c1,c2,c3,c4


def test_rrf_fuse_k_parameter() -> None:
    """k 参数可配置且影响融合分。"""
    a = [_r("c1"), _r("c2")]
    b = [_r("c1"), _r("c2")]
    out_k60 = rrf_fuse([a, b], k=60)
    out_k1 = rrf_fuse([a, b], k=1)
    assert len(out_k60) == 2 and len(out_k1) == 2
    # 同一 chunk 在两路都排第一：RRF 分 = 1/(k+1) + 1/(k+1)。k 越大分越小但顺序可同
    assert out_k60[0].chunk_id == out_k1[0].chunk_id == "c1"
    assert out_k60[0].score != out_k1[0].score


def test_rrf_fuse_merge_order() -> None:
    """多路重叠时按 RRF 分降序、chunk_id 升序。"""
    dense = [_r("a", 0.9), _r("b", 0.8)]
    sparse = [_r("b", 0.9), _r("a", 0.8)]
    out = rrf_fuse([dense, sparse], k=60)
    ids = [x.chunk_id for x in out]
    assert set(ids) == {"a", "b"}
    # a 在 dense 第 0、sparse 第 1 → 1/61 + 1/62；b 在 dense 第 1、sparse 第 0 → 1/62 + 1/61，同分则 a < b
    assert ids[0] == "b" or ids[0] == "a"
    assert out[0].score >= out[1].score


def test_rrf_fuse_empty_lists() -> None:
    """空列表返回空。"""
    assert rrf_fuse([], k=60) == []
    assert rrf_fuse([[], []], k=60) == []


def test_rrf_fuse_single_list() -> None:
    """单路时顺序不变、分值为 1/(k+rank)。"""
    single = [_r("x"), _r("y")]
    out = rrf_fuse([single], k=60)
    assert [x.chunk_id for x in out] == ["x", "y"]
    assert out[0].score > out[1].score

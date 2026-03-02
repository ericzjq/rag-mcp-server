"""
SparseEncoder（C9）：对 chunks 建立 BM25 所需统计，输出 term weights 结构，供 bm25_indexer 使用。
"""

import re
from typing import Any, List, Optional

from core.types import Chunk, ChunkRecord


def _tokenize(text: str) -> List[str]:
    """简单分词：按非字母数字切分、小写，过滤空串。"""
    if not text or not text.strip():
        return []
    lowered = text.strip().lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    return [t for t in tokens if t]


def _term_frequencies(tokens: List[str]) -> dict[str, float]:
    """统计 token 出现次数，返回 term -> count (float)。"""
    counts: dict[str, float] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0.0) + 1.0
    return counts


class SparseEncoder:
    """将 Chunk 文本转为稀疏表示（term -> weight），输出 ChunkRecord（含 sparse_vector）。"""

    def encode(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[ChunkRecord]:
        """
        对 chunks 批量做稀疏编码，输出可用于 bm25_indexer 的 ChunkRecord 列表。

        每个 chunk 的 sparse_vector 为 Dict[str, float]，表示 term -> 权重（当前为词频 tf）。
        空文本的 chunk 对应 sparse_vector 为空 dict。

        Args:
            chunks: 输入 Chunk 列表。
            trace: 可选追踪上下文（预留）。

        Returns:
            ChunkRecord 列表，每项含 id、text、metadata、sparse_vector；dense_vector 为 None。
        """
        out: List[ChunkRecord] = []
        for c in chunks:
            tokens = _tokenize(c.text)
            weights = _term_frequencies(tokens)
            metadata = dict(c.metadata) if isinstance(c.metadata, dict) else {}
            out.append(
                ChunkRecord(
                    id=c.id,
                    text=c.text,
                    metadata=metadata,
                    dense_vector=None,
                    sparse_vector=weights,
                )
            )
        return out

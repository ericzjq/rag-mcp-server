"""
BatchProcessor（C10）：将 chunks 分 batch，驱动 dense/sparse 编码，记录批次耗时（为 trace 预留）。
"""

import time
from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk, ChunkRecord

from ingestion.embedding.dense_encoder import DenseEncoder
from ingestion.embedding.sparse_encoder import SparseEncoder


class BatchProcessor:
    """按 batch_size 分批调用 DenseEncoder 与 SparseEncoder，合并为带 dense_vector 与 sparse_vector 的 ChunkRecord，记录每批耗时。"""

    def __init__(
        self,
        settings: Settings,
        dense_encoder: Optional[DenseEncoder] = None,
        sparse_encoder: Optional[SparseEncoder] = None,
    ) -> None:
        self._settings = settings
        self._dense = dense_encoder if dense_encoder is not None else DenseEncoder(settings)
        self._sparse = sparse_encoder if sparse_encoder is not None else SparseEncoder()

    def process(
        self,
        chunks: List[Chunk],
        batch_size: int = 2,
        trace: Optional[Any] = None,
    ) -> List[ChunkRecord]:
        """
        将 chunks 按 batch_size 分批，每批先 dense 再 sparse 编码，合并后按原顺序返回；记录每批耗时到 trace。

        Args:
            chunks: 输入 Chunk 列表。
            batch_size: 每批大小（最后一批可不足）。
            trace: 可选 TraceContext；若提供则 record_stage("batch_timings", [...])。

        Returns:
            ChunkRecord 列表，每项含 dense_vector 与 sparse_vector，顺序与 chunks 一致。
        """
        if not chunks:
            return []
        batch_timings: List[dict] = []
        result: List[ChunkRecord] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            t0 = time.perf_counter()
            dense_records = self._dense.encode(batch, trace=trace)
            sparse_records = self._sparse.encode(batch, trace=trace)
            elapsed = time.perf_counter() - t0
            batch_timings.append({"batch_index": len(batch_timings), "elapsed_sec": elapsed})
            for dr, sr in zip(dense_records, sparse_records):
                result.append(
                    ChunkRecord(
                        id=dr.id,
                        text=dr.text,
                        metadata=dict(dr.metadata) if dr.metadata else {},
                        dense_vector=dr.dense_vector,
                        sparse_vector=sr.sparse_vector,
                    )
                )
        if trace is not None and hasattr(trace, "record_stage"):
            trace.record_stage("batch_timings", batch_timings)
        return result

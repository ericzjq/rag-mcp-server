"""
DenseEncoder（C8）：将 chunks.text 批量送入 BaseEmbedding，产出带 dense_vector 的 ChunkRecord。
"""

from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk, ChunkRecord

from libs.embedding.base_embedding import BaseEmbedding
from libs.embedding.embedding_factory import create as create_embedding


class DenseEncoder:
    """批量将 Chunk 文本编码为 dense 向量，输出 ChunkRecord（含 dense_vector）。"""

    def __init__(self, settings: Settings, embedding_client: Optional[BaseEmbedding] = None) -> None:
        self._settings = settings
        self._embedding = embedding_client if embedding_client is not None else create_embedding(settings)

    def encode(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[ChunkRecord]:
        """
        对 chunks 批量做 dense 编码，返回与 chunks 等长的 ChunkRecord 列表，向量维度一致。

        Args:
            chunks: 输入 Chunk 列表。
            trace: 可选追踪上下文。

        Returns:
            ChunkRecord 列表，每项含 id、text、metadata、dense_vector；数量与 chunks 一致，向量维度一致。
        """
        if not chunks:
            return []
        texts = [c.text for c in chunks]
        vectors = self._embedding.embed(texts, trace=trace)
        if len(vectors) != len(chunks):
            raise ValueError(
                f"DenseEncoder: embed 返回向量数 {len(vectors)} 与 chunks 数 {len(chunks)} 不一致"
            )
        dim = len(vectors[0]) if vectors else 0
        for i, v in enumerate(vectors):
            if len(v) != dim:
                raise ValueError(f"DenseEncoder: 向量维度不一致，chunk index {i}")
        return [
            ChunkRecord(
                id=c.id,
                text=c.text,
                metadata=dict(c.metadata) if isinstance(c.metadata, dict) else {},
                dense_vector=list(vectors[i]),
                sparse_vector=None,
            )
            for i, c in enumerate(chunks)
        ]

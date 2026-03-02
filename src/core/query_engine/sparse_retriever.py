"""
SparseRetriever（D3）：从 BM25 索引查询 keywords，再按 chunk_id 从 VectorStore 取 text/metadata，组装 RetrievalResult。
"""

from pathlib import Path
from typing import Any, List, Optional

from core.settings import Settings
from core.types import RetrievalResult

from ingestion.storage.bm25_indexer import BM25Indexer
from libs.vector_store.base_vector_store import BaseVectorStore
from libs.vector_store.vector_store_factory import create as create_vector_store

DEFAULT_BM25_INDEX_DIR = "data/db/bm25"


class SparseRetriever:
    """BM25 关键词检索 + VectorStore.get_by_ids 取正文与元数据，返回 RetrievalResult 列表。"""

    def __init__(
        self,
        settings: Settings,
        *,
        bm25_indexer: Optional[BM25Indexer] = None,
        vector_store: Optional[BaseVectorStore] = None,
        bm25_index_dir: str = DEFAULT_BM25_INDEX_DIR,
    ) -> None:
        self._settings = settings
        self._bm25 = bm25_indexer if bm25_indexer is not None else BM25Indexer(index_dir=bm25_index_dir)
        self._store = vector_store if vector_store is not None else create_vector_store(settings)

    def retrieve(
        self,
        keywords: List[str],
        top_k: int,
        trace: Optional[Any] = None,
    ) -> List[RetrievalResult]:
        """
        对 keywords 做 BM25 检索，再按 chunk_id 拉取 text/metadata，合并为 RetrievalResult 列表。

        Args:
            keywords: 关键词列表（通常来自 QueryProcessor.process().keywords）。
            top_k: 返回条数。
            trace: 可选追踪上下文。

        Returns:
            含 chunk_id、score、text、metadata 的列表（按 BM25 分数降序）。
        """
        if not keywords:
            return []
        # 若索引未加载则尝试从默认路径 load
        if self._bm25._n == 0:
            index_path = Path(self._bm25._index_dir) / "index.json"
            if index_path.exists():
                self._bm25.load(str(index_path))
        id_score_pairs = self._bm25.query_with_scores(keywords, top_k=top_k)
        if not id_score_pairs:
            return []
        ids = [cid for cid, _ in id_score_pairs]
        score_by_id = {cid: sc for cid, sc in id_score_pairs}
        records = self._store.get_by_ids(ids)
        record_by_id = {r["id"]: r for r in records}
        out: List[RetrievalResult] = []
        for cid in ids:
            score = score_by_id.get(cid, 0.0)
            rec = record_by_id.get(cid) or {}
            out.append(
                RetrievalResult(
                    chunk_id=cid,
                    score=score,
                    text=rec.get("text", ""),
                    metadata=dict(rec.get("metadata", {})),
                )
            )
        return out

"""
Chroma 向量存储实现。

支持本地持久化目录（persist_directory），upsert(records) 与 query(vector, top_k, filters)。
返回结果含 id、score（相似度）、metadata、text（来自 document）。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.settings import Settings

from libs.vector_store.base_vector_store import (
    BaseVectorStore,
    QueryResultItem,
    VectorStoreRecord,
)

DEFAULT_COLLECTION_NAME = "default"


class ChromaStore(BaseVectorStore):
    """基于 ChromaDB 的向量存储，支持持久化与 metadata 过滤。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._persist_directory = Path(settings.vector_store.persist_directory)
        self._persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
            except ImportError as e:
                raise RuntimeError(
                    "ChromaStore 需要 chromadb，请 pip install chromadb"
                ) from e
            self._client = chromadb.PersistentClient(path=str(self._persist_directory))
            self._collection = self._client.get_or_create_collection(
                name=DEFAULT_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def upsert(
        self,
        records: List[VectorStoreRecord],
        trace: Optional[Any] = None,
    ) -> None:
        if not records:
            return
        coll = self._get_collection()
        ids = [r["id"] for r in records]
        embeddings = [r["vector"] for r in records]
        metadatas = [r.get("metadata", {}) for r in records]
        # Chroma 要求 metadata 值均为 str/int/float/bool；嵌套 dict 需序列化或展平
        metadatas_safe = []
        for m in metadatas:
            safe = {}
            for k, v in m.items():
                if v is None or isinstance(v, (str, int, float, bool)):
                    safe[k] = v
                else:
                    safe[k] = str(v)
            metadatas_safe.append(safe)
        documents = [
            m.get("text", "") if isinstance(m, dict) else ""
            for m in metadatas
        ]
        coll.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas_safe,
            documents=documents,
        )

    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        trace: Optional[Any] = None,
    ) -> List[QueryResultItem]:
        coll = self._get_collection()
        where = self._to_chroma_where(filters) if filters else None
        n = max(1, top_k)
        result = coll.query(
            query_embeddings=[vector],
            n_results=n,
            where=where,
            include=["metadatas", "documents", "distances"],
        )
        ids = result["ids"][0] if result["ids"] else []
        distances = result["distances"][0] if result.get("distances") else []
        metadatas = result["metadatas"][0] if result.get("metadatas") else []
        documents = result["documents"][0] if result.get("documents") else []
        out: List[QueryResultItem] = []
        for i, vid in enumerate(ids):
            # cosine distance: 0 = same, 2 = opposite → similarity = 1 - distance/2
            dist = distances[i] if i < len(distances) else 0.0
            score = float(1.0 - (dist / 2.0)) if isinstance(dist, (int, float)) else 0.0
            meta = metadatas[i] if i < len(metadatas) else {}
            text = documents[i] if i < len(documents) else ""
            item = {"id": vid, "score": score, "metadata": meta or {}}
            if text is not None:
                item["text"] = text
            out.append(item)
        return out

    def _to_chroma_where(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将简单 filters 转为 Chroma where 格式（标量等值）。"""
        if not filters:
            return None
        out = {}
        for k, v in filters.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                out[k] = v
        return out if out else None

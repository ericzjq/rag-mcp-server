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
            item = {
                "id": vid,
                "score": score,
                "metadata": meta or {},
                "text": text if text is not None else "",
            }
            out.append(item)
        return out

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """根据 id 批量获取 documents 与 metadatas。"""
        if not ids:
            return []
        coll = self._get_collection()
        result = coll.get(ids=ids, include=["metadatas", "documents"])
        out: List[Dict[str, Any]] = []
        id_list = result["ids"] if result.get("ids") else []
        metadatas = result.get("metadatas") or []
        documents = result.get("documents") or []
        for i, vid in enumerate(id_list):
            meta = metadatas[i] if i < len(metadatas) else {}
            text = documents[i] if i < len(documents) else ""
            out.append({
                "id": vid,
                "text": text if text is not None else "",
                "metadata": meta or {},
            })
        return out

    def get_collection_stats(self) -> Dict[str, Any]:
        """返回集合统计（如 chunk 数量），供 Dashboard 总览展示。"""
        try:
            coll = self._get_collection()
            return {"count": coll.count()}
        except Exception:
            return {"count": 0}

    def get_ids_by_metadata(self, filters: Dict[str, Any]) -> List[str]:
        """按 metadata 条件查询，返回匹配的 id 列表（用于按 source_path 列出/删除 chunk）。"""
        if not filters:
            return []
        where = self._to_chroma_where(filters)
        if not where:
            return []
        coll = self._get_collection()
        result = coll.get(where=where, include=[])
        ids = result.get("ids") or []
        return list(ids)

    def delete_by_metadata(self, filters: Dict[str, Any]) -> int:
        """按 metadata 条件删除记录，返回删除条数。"""
        ids = self.get_ids_by_metadata(filters)
        if not ids:
            return 0
        coll = self._get_collection()
        coll.delete(ids=ids)
        return len(ids)

    def delete_ids(self, ids: List[str]) -> int:
        """按 id 列表删除记录，返回删除条数。"""
        if not ids:
            return 0
        coll = self._get_collection()
        coll.delete(ids=ids)
        return len(ids)

    def get_all(self, limit: int = 50000) -> List[Dict[str, Any]]:
        """拉取集合内全部记录（id、text、metadata），用于按内容去重等。"""
        coll = self._get_collection()
        result = coll.get(limit=limit, include=["documents", "metadatas"])
        id_list = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        out: List[Dict[str, Any]] = []
        for i, vid in enumerate(id_list):
            text = (documents[i] if i < len(documents) else "") or ""
            meta = (metadatas[i] if i < len(metadatas) else None) or {}
            out.append({"id": vid, "text": text, "metadata": meta})
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

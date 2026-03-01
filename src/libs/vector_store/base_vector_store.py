"""
VectorStore 抽象基类。

所有向量库实现（Chroma、Qdrant、Pinecone 等）均继承此接口。B4 先定义契约，不接真实 DB。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 单条写入记录：id、向量、元数据（与 ingestion/retrieval 契约一致）
# 具体实现可扩展为含 sparse_vector、text 等字段
VectorStoreRecord = Dict[str, Any]  # 至少含 "id", "vector", "metadata"

# 单条查询结果：id、相似度分数、可选元数据
QueryResultItem = Dict[str, Any]  # 至少含 "id", "score", 可选 "metadata"


class BaseVectorStore(ABC):
    """向量存储抽象基类，统一 upsert 与 query 接口。"""

    @abstractmethod
    def upsert(
        self,
        records: List[VectorStoreRecord],
        trace: Optional[Any] = None,
    ) -> None:
        """
        批量写入或更新向量记录（幂等：同 id 覆盖）。

        Args:
            records: 记录列表，每项至少含 "id" (str)、"vector" (List[float])、"metadata" (dict)。
            trace: 可选追踪上下文，当前可传 None。
        """
        ...

    @abstractmethod
    def query(
        self,
        vector: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        trace: Optional[Any] = None,
    ) -> List[QueryResultItem]:
        """
        按向量相似度检索 Top-K 结果。

        Args:
            vector: 查询向量。
            top_k: 返回的最大条数。
            filters: 可选的 metadata 过滤条件（如 collection、doc_type）。
            trace: 可选追踪上下文，当前可传 None。

        Returns:
            结果列表，每项至少含 "id" (str)、"score" (float)，可选 "metadata"。
        """
        ...

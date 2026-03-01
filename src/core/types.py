"""
核心数据类型/契约（C1）：全链路共用 Document / Chunk / ChunkRecord。

- Document：原始文档，含 text 与 metadata（至少 source_path，可选 metadata.images）。
- Chunk：文档切分片段，含 start_offset/end_offset、可选 source_ref。
- ChunkRecord：存储/检索载体，含可选 dense_vector/sparse_vector（C8~C12 演进）。

metadata.images 规范见 C1；文本中图片占位符为 [IMAGE: {image_id}]。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# metadata.images 单条结构（多模态）
# id: 全局唯一；path: 存储路径；page/text_offset/text_length: 占位符定位；position: 可选
# ---------------------------------------------------------------------------
ImageRef = Dict[str, Any]  # id, path, page?, text_offset, text_length, position?


@dataclass(frozen=True)
class Document:
    """原始文档：id、正文 text、metadata（至少含 source_path，可选 images）。"""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "text": self.text, "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class Chunk:
    """文档切分片段：id、text、metadata、在原文中的偏移、可选 source_ref。"""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_offset: int = 0
    end_offset: int = 0
    source_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }
        if self.source_ref is not None:
            out["source_ref"] = self.source_ref
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            metadata=dict(data.get("metadata", {})),
            start_offset=int(data.get("start_offset", 0)),
            end_offset=int(data.get("end_offset", 0)),
            source_ref=data.get("source_ref"),
        )


@dataclass
class ChunkRecord:
    """存储/检索用记录：id、text、metadata，可选 dense_vector / sparse_vector（C8~C12）。"""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    dense_vector: Optional[List[float]] = None
    sparse_vector: Optional[Dict[str, float]] = None  # 或 List[Tuple[int, float]] 按需

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
        }
        if self.dense_vector is not None:
            out["dense_vector"] = list(self.dense_vector)
        if self.sparse_vector is not None:
            out["sparse_vector"] = dict(self.sparse_vector)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRecord":
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            metadata=dict(data.get("metadata", {})),
            dense_vector=data.get("dense_vector"),
            sparse_vector=data.get("sparse_vector"),
        )

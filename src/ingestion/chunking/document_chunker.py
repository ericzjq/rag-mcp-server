"""
DocumentChunker（C4）：libs.splitter 与 Ingestion 的适配器，Document → List[Chunk]。

增值：Chunk ID 生成、元数据继承、chunk_index、source_ref、List[str] → List[Chunk]。
"""

import hashlib
from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk, Document

from libs.splitter.base_splitter import BaseSplitter
from libs.splitter.splitter_factory import create as create_splitter


def _generate_chunk_id(doc_id: str, index: int, text: str) -> str:
    """生成稳定 Chunk ID：{doc_id}_{index:04d}_{hash_8chars}。"""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{doc_id}_{index:04d}_{h}"


def _inherit_metadata(document: Document, chunk_index: int) -> dict:
    """将 Document.metadata 复制并添加 chunk_index。"""
    meta = dict(document.metadata)
    meta["chunk_index"] = chunk_index
    return meta


class DocumentChunker:
    """将 Document 切分为 List[Chunk]，委托 libs.splitter 做文本切分，再附加业务字段。"""

    def __init__(self, settings: Settings, splitter: Optional[BaseSplitter] = None) -> None:
        self._settings = settings
        self._splitter = splitter if splitter is not None else create_splitter(settings)

    def split_document(self, document: Document, trace: Optional[Any] = None) -> List[Chunk]:
        """完整转换：Document.text → splitter.split_text → List[Chunk]（含 id、metadata、source_ref、offset）。"""
        if not (document.text or "").strip():
            return []
        segments = self._splitter.split_text(document.text.strip(), trace=trace)
        chunks: List[Chunk] = []
        start_offset = 0
        for i, text in enumerate(segments):
            chunk_id = _generate_chunk_id(document.id, i, text)
            meta = _inherit_metadata(document, i)
            end_offset = start_offset + len(text)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    metadata=meta,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    source_ref=document.id,
                )
            )
            start_offset = end_offset
        return chunks

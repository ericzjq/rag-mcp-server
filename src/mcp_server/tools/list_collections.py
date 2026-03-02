"""
list_collections Tool（E4）：列出 data/documents/ 下集合名（子目录名），返回 MCP content + structuredContent。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def list_collections(
    *,
    documents_base: str = "data/documents",
    work_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    列出文档根目录下的集合名（直接子目录名）。用于测试可传入 work_dir 或 documents_base 覆盖。
    """
    base = Path(work_dir or os.getcwd())
    doc_path = base / documents_base if not os.path.isabs(documents_base) else Path(documents_base)
    if not doc_path.is_dir():
        return _format_result([])

    names: List[str] = []
    for entry in doc_path.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            names.append(entry.name)
    names.sort()

    return _format_result(names)


def _format_result(collections: List[str]) -> Dict[str, Any]:
    if not collections:
        text = "当前无文档集合。可先使用 ingest 摄取文档。"
    else:
        text = "集合列表：\n\n" + "\n".join(f"- {c}" for c in collections)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"collections": collections},
    }


LIST_COLLECTIONS_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}

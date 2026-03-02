"""
get_document_summary Tool（E5）：按 doc_id 返回 title/summary/tags；不存在时返回规范错误。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_METADATA_PATH = "data/db/document_metadata.json"


def get_document_summary(
    doc_id: str,
    *,
    metadata_path: Optional[str] = None,
    work_dir: Optional[str] = None,
    _store: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    按 doc_id 查询文档摘要（title/summary/tags）。数据来源：_store（测试注入）或 metadata 文件。
    不存在时返回规范错误（content + structuredContent.error），不抛异常。
    """
    if _store is not None:
        meta = _store.get(doc_id) if doc_id else None
    else:
        base = Path(work_dir or os.getcwd())
        path = metadata_path or _DEFAULT_METADATA_PATH
        if not os.path.isabs(path):
            path = str(base / path)
        meta = _load_doc_meta(path, doc_id)

    if meta is None:
        return _format_error(doc_id)

    title = meta.get("title", "")
    summary = meta.get("summary", "")
    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return {
        "content": [
            {
                "type": "text",
                "text": f"**{title}**\n\n{summary}\n\n标签: {', '.join(tags) if tags else '无'}",
            },
        ],
        "structuredContent": {
            "doc_id": doc_id,
            "title": title,
            "summary": summary,
            "tags": tags,
        },
    }


def _load_doc_meta(path: str, doc_id: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data.get(doc_id)


def _format_error(doc_id: str) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"文档不存在: {doc_id}"}],
        "structuredContent": {"error": "not_found", "doc_id": doc_id},
    }


GET_DOCUMENT_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_id": {"type": "string", "description": "文档 ID"},
    },
    "required": ["doc_id"],
}

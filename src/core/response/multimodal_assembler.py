"""
MultimodalAssembler（E6）：命中 chunk 含 image_refs 时读取图片并 base64 返回 ImageContent。
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.types import RetrievalResult

logger = logging.getLogger(__name__)

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _get_image_refs(result: RetrievalResult) -> List[Dict[str, Any]]:
    """从 result.metadata.images 取 image_refs（id + path）。"""
    meta = result.metadata or {}
    images = meta.get("images")
    if not isinstance(images, list):
        return []
    return [img for img in images if isinstance(img, dict) and img.get("path")]


def _mime_for_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    return _MIME_BY_EXT.get(ext, "image/png")


def assemble(
    retrieval_results: List[RetrievalResult],
    work_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    从检索结果中收集 image_refs（metadata.images），读取图片文件并转为 MCP ImageContent。
    返回 [ {"type": "image", "mimeType": "...", "data": "<base64>"}, ... ]。
    路径为相对时以 work_dir 为根；缺失文件跳过并打日志。
    """
    base = Path(work_dir).resolve() if work_dir else Path.cwd()
    out: List[Dict[str, Any]] = []
    seen_paths: set = set()

    for r in retrieval_results:
        for ref in _get_image_refs(r):
            path_val = ref.get("path", "").strip()
            if not path_val:
                continue
            path = Path(path_val)
            if not path.is_absolute():
                path = (base / path).resolve()
            path_str = str(path)
            if path_str in seen_paths:
                continue
            seen_paths.add(path_str)
            if not path.is_file():
                logger.warning("Image file not found: %s", path)
                continue
            try:
                raw = path.read_bytes()
                b64 = base64.standard_b64encode(raw).decode("ascii")
                mime = _mime_for_path(path_str)
                out.append({"type": "image", "mimeType": mime, "data": b64})
            except OSError as e:
                logger.warning("Failed to read image %s: %s", path, e)
    return out

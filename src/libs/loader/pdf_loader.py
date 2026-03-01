"""
PDF Loader（C3）：从 PDF 提取文本与图片，产出 Document（C1 契约）；图片提取失败时降级不阻塞。
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List

from core.types import Document

from libs.loader.base_loader import BaseLoader

logger = logging.getLogger(__name__)

DEFAULT_IMAGES_DIR = "data/images"


def _doc_id_from_path(path: str) -> str:
    """基于路径生成稳定文档 ID（如用于 doc_hash）。"""
    return hashlib.sha256(Path(path).resolve().as_posix().encode()).hexdigest()[:16]


def _ensure_images_dir(base_dir: str, doc_hash: str) -> Path:
    """确保 data/images/{doc_hash}/ 存在并返回该 Path。"""
    d = Path(base_dir) / doc_hash
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_text_and_images(
    path: str,
    images_base_dir: str,
    doc_hash: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """从 PDF 提取文本与图片；返回 (全文含占位符, metadata.images 列表)。图片失败仅打日志。"""
    from pypdf import PdfReader

    reader = PdfReader(path)
    text_parts: List[str] = []
    images_meta: List[Dict[str, Any]] = []
    try:
        images_dir = _ensure_images_dir(images_base_dir, doc_hash)
    except OSError as e:
        logger.warning("PDF 图片存储目录创建失败，跳过图片提取: %s", e)
        images_dir = None

    for page_idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        page_fragments: List[str] = [page_text]
        if images_dir is not None:
            try:
                img_list = getattr(page, "images", None) or []
                seq = 0
                for img_obj in img_list:
                    try:
                        data = getattr(img_obj, "data", None)
                        if not data:
                            continue
                        ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
                        image_id = f"{doc_hash}_{page_idx}_{seq}"
                        out_path = images_dir / f"{image_id}{ext}"
                        out_path.write_bytes(data)
                        placeholder = f"[IMAGE: {image_id}]"
                        full_so_far = "\n".join(text_parts) + "\n".join(page_fragments)
                        text_offset = len(full_so_far)
                        text_length = len(placeholder)
                        page_fragments.append(placeholder)
                        images_meta.append({
                            "id": image_id,
                            "path": str(out_path),
                            "page": page_idx,
                            "text_offset": text_offset,
                            "text_length": text_length,
                            "position": {},
                        })
                        seq += 1
                    except Exception as e:
                        logger.warning("PDF 单张图片提取失败 (page=%s): %s", page_idx, e)
            except Exception as e:
                logger.warning("PDF 页面图片提取失败 (page=%s): %s", page_idx, e)
        text_parts.append("\n".join(page_fragments))
        if page_idx < len(reader.pages) - 1:
            text_parts.append("\n")

    full_text = "\n".join(text_parts) if text_parts else ""
    return full_text, images_meta


class PdfLoader(BaseLoader):
    """从 PDF 加载文档：文本 + 可选图片（C1 占位符与 metadata.images）；图片失败不阻塞。"""

    def __init__(self, images_base_dir: str = DEFAULT_IMAGES_DIR) -> None:
        self._images_base_dir = images_base_dir

    def load(self, path: str) -> Document:
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"PDF 不存在: {path}")
        doc_hash = _doc_id_from_path(path)
        doc_id = doc_hash

        try:
            text, images = _extract_text_and_images(path, self._images_base_dir, doc_hash)
        except Exception as e:
            logger.warning("PDF 解析失败，尝试仅提取文本: %s", e)
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                text = "\n".join((p.extract_text() or "") for p in reader.pages)
                images = []
            except Exception:
                raise

        metadata: Dict[str, Any] = {"source_path": path}
        if images:
            metadata["images"] = images
        return Document(id=doc_id, text=text, metadata=metadata)

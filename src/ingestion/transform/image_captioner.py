"""
ImageCaptioner（C7）：当启用 Vision LLM 且存在 image_refs 时生成 caption 写回 chunk metadata；
禁用/不可用/异常时降级，标记 has_unprocessed_images，不阻塞 ingestion。
"""

import logging
from pathlib import Path
from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk

from ingestion.transform.base_transform import BaseTransform

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = "config/prompts/image_captioning.txt"


def _get_image_refs(chunk: Chunk) -> List[dict]:
    """从 chunk.metadata.images 取 image_refs（C1 规范）。"""
    meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}
    images = meta.get("images")
    if not isinstance(images, list):
        return []
    return [img for img in images if isinstance(img, dict) and img.get("id") and img.get("path")]


def _image_refs_in_chunk_text(chunk: Chunk, image_refs: List[dict]) -> List[dict]:
    """
    只保留「在本 chunk 正文中出现占位符」的 image_refs。
    文档级 metadata.images 被复制到了每个 chunk，若不做过滤会对同一张图重复调用 LLM（每 chunk 一次）。
    """
    text = chunk.text or ""
    return [ref for ref in image_refs if ref.get("id") and f"[IMAGE: {ref['id']}]" in text]


def _load_prompt(path: Optional[Path] = None) -> str:
    path = path or Path(DEFAULT_PROMPT_PATH)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "Describe this image briefly in one sentence."


class ImageCaptioner(BaseTransform):
    """为含 image_refs 的 chunk 生成 caption，写回 metadata；降级时标记 has_unprocessed_images。"""

    def __init__(
        self,
        settings: Settings,
        *,
        vision_llm_client: Optional[Any] = None,
        prompt_path: Optional[Path] = None,
        max_images: Optional[int] = None,
    ) -> None:
        """
        Args:
            max_images: 单次 transform 中最多对几张图调用 Vision LLM；None 表示不限制。用于调试或控制耗时。
        """
        self._settings = settings
        self._vision_llm = vision_llm_client
        self._prompt_path = prompt_path
        self._prompt: Optional[str] = None
        self._max_images = max_images

    def _get_vision_llm(self):
        if self._vision_llm is not None:
            return self._vision_llm
        if self._settings.vision_llm is None:
            return None
        from libs.llm.llm_factory import create_vision_llm
        return create_vision_llm(self._settings)

    def _get_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = _load_prompt(self._prompt_path)
        return self._prompt

    def transform(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[Chunk]:
        result: List[Chunk] = []
        captioned_count = 0  # 本次 transform 已 caption 的图片数，用于 max_images 限制
        caption_cache: dict = {}  # image_id -> caption，同一次 transform 内同一张图只调一次 LLM
        for c in chunks:
            try:
                image_refs = _get_image_refs(c)
                # 只处理本 chunk 正文中实际出现 [IMAGE: id] 的图，避免因「每 chunk 都继承文档级 images」导致的重复调用
                image_refs = _image_refs_in_chunk_text(c, image_refs)
                if not image_refs:
                    result.append(c)
                    continue
                vision_llm = self._get_vision_llm()
                if vision_llm is None:
                    meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                    meta["has_unprocessed_images"] = True
                    result.append(
                        Chunk(
                            id=c.id,
                            text=c.text,
                            metadata=meta,
                            start_offset=c.start_offset,
                            end_offset=c.end_offset,
                            source_ref=c.source_ref,
                        )
                    )
                    continue
                prompt = self._get_prompt()
                captions: dict = {}
                for ref in image_refs:
                    img_id = ref.get("id", "")
                    path = ref.get("path", "")
                    if not img_id or not path:
                        continue
                    if img_id in caption_cache:
                        captions[img_id] = caption_cache[img_id]
                        continue
                    if self._max_images is not None and captioned_count >= self._max_images:
                        logger.debug("ImageCaptioner 已达 max_images=%d，跳过 id=%s", self._max_images, img_id)
                        continue
                    try:
                        resp = vision_llm.chat_with_image(prompt, path, trace=trace)
                        caption_text = (resp.content or "").strip()
                        captions[img_id] = caption_text
                        caption_cache[img_id] = caption_text
                        captioned_count += 1
                        logger.info("ImageCaptioner 图转文 id=%s 输出: %s", img_id, caption_text[:300] + ("..." if len(caption_text) > 300 else ""))
                    except Exception as e:
                        logger.warning("ImageCaptioner 单张图片失败 id=%s: %s", img_id, e)
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                if captions:
                    meta["image_captions"] = captions
                if len(captions) < len(image_refs):
                    meta["has_unprocessed_images"] = True
                result.append(
                    Chunk(
                        id=c.id,
                        text=c.text,
                        metadata=meta,
                        start_offset=c.start_offset,
                        end_offset=c.end_offset,
                        source_ref=c.source_ref,
                    )
                )
            except Exception as e:
                logger.warning("ImageCaptioner 单条 chunk 异常 id=%s: %s", c.id, e)
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                meta["has_unprocessed_images"] = True
                result.append(
                    Chunk(
                        id=c.id,
                        text=c.text,
                        metadata=meta,
                        start_offset=c.start_offset,
                        end_offset=c.end_offset,
                        source_ref=c.source_ref,
                    )
                )
        return result

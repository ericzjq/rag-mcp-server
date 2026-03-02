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
    ) -> None:
        self._settings = settings
        self._vision_llm = vision_llm_client
        self._prompt_path = prompt_path
        self._prompt: Optional[str] = None

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
        for c in chunks:
            try:
                image_refs = _get_image_refs(c)
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
                    try:
                        resp = vision_llm.chat_with_image(prompt, path, trace=trace)
                        captions[img_id] = (resp.content or "").strip()
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

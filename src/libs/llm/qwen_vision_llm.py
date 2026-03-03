"""
Qwen Vision LLM：通过阿里云 DashScope 兼容模式调用 Qwen-VL-Max 进行图像理解。
DashScope 提供 OpenAI 兼容接口，请求格式为 chat completions + image_url（data URL）。
"""

import base64
import io
from pathlib import Path
from typing import Any, Union

from core.settings import Settings
from libs.llm.base_vision_llm import BaseVisionLLM, ChatResponse

PROVIDER_NAME = "qwen"
# DashScope OpenAI 兼容模式（支持 Qwen-VL-Max 等多模态模型）
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-vl-max"


def _resize_image_if_needed(image_bytes: bytes, max_size: int) -> bytes:
    if max_size <= 0:
        return image_bytes
    try:
        from PIL import Image
    except ImportError:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return image_bytes
    w, h = img.size
    if w <= max_size and h <= max_size:
        return image_bytes
    if w >= h:
        new_w, new_h = max_size, max(1, int(h * max_size / w))
    else:
        new_w, new_h = max(1, int(w * max_size / h)), max_size
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


def _load_image_bytes(image_path: Union[str, bytes]) -> bytes:
    if isinstance(image_path, bytes):
        return image_path
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"{PROVIDER_NAME}: 图片文件不存在: {path}")
    return path.read_bytes()


def _mime_from_path(path: Union[str, Path]) -> str:
    p = Path(path) if isinstance(path, str) else path
    suf = (p.suffix or "").lower()
    if suf in (".png",):
        return "image/png"
    if suf in (".jpg", ".jpeg", ".gif", ".webp"):
        return "image/jpeg" if suf == ".jpg" else f"image/{suf[1:]}"
    return "image/png"


class QwenVisionLLM(BaseVisionLLM):
    """Qwen-VL-Max（DashScope OpenAI 兼容多模态接口）实现。"""

    def __init__(self, settings: Settings) -> None:
        if settings.vision_llm is None:
            raise ValueError(f"{PROVIDER_NAME}: vision_llm 未配置")
        self._settings = settings
        self._vl = settings.vision_llm
        self._api_key = (self._vl.api_key or "").strip() or None
        self._base_url = (self._vl.base_url or "").strip() or DEFAULT_BASE_URL
        self._model = (self._vl.model or "").strip() or DEFAULT_MODEL
        self._max_image_size = max(0, getattr(self._vl, "max_image_size", 2048))
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(f"{PROVIDER_NAME}: 需要 openai 包") from e
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url or None,
            )
        return self._client

    def _image_to_data_url(self, image_path: Union[str, bytes]) -> str:
        raw = _load_image_bytes(image_path)
        resized = _resize_image_if_needed(raw, self._max_image_size)
        b64 = base64.standard_b64encode(resized).decode("ascii")
        mime = _mime_from_path(image_path) if isinstance(image_path, str) else "image/png"
        return f"data:{mime};base64,{b64}"

    def chat_with_image(
        self,
        text: str,
        image_path: Union[str, bytes],
        trace: Any = None,
    ) -> ChatResponse:
        try:
            data_url = self._image_to_data_url(image_path)
        except FileNotFoundError as e:
            raise ValueError(str(e)) from e

        content = [
            {"type": "text", "text": text or ""},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        messages = [{"role": "user", "content": content}]

        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except Exception as e:
            err_msg = str(e)
            if self._api_key and self._api_key in err_msg:
                err_msg = err_msg.replace(self._api_key, "***")
            raise ValueError(f"{PROVIDER_NAME}: {type(e).__name__} — {err_msg}") from e

        choice = resp.choices[0] if resp.choices else None
        if not choice or not getattr(choice, "message", None):
            return ChatResponse(content="")
        return ChatResponse(content=(choice.message.content or "").strip())

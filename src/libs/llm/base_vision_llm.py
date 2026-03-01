"""
Vision LLM 抽象基类。

支持文本+图片的多模态输入（图片为路径或 base64 bytes），为 C7 ImageCaptioner 等提供底层抽象。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Union

# 避免循环导入
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.settings import Settings


@dataclass(frozen=True)
class ChatResponse:
    """Vision LLM 调用返回，含文本内容；可扩展 role、usage 等。"""
    content: str


class BaseVisionLLM(ABC):
    """Vision LLM 抽象基类，统一 chat_with_image 接口。支持图片路径或 base64。"""

    @abstractmethod
    def chat_with_image(
        self,
        text: str,
        image_path: Union[str, bytes],
        trace: Any = None,
    ) -> ChatResponse:
        """
        根据文本与图片生成回复（如图片描述）。

        Args:
            text: 与图片一起发送的文本（如 prompt）。
            image_path: 图片路径（str）或 base64 编码的图片数据（bytes）。
            trace: 可选追踪上下文（TraceContext），当前可传 None。

        Returns:
            ChatResponse，含 content 文本。
        """
        ...

"""
LLM 抽象基类。

所有 LLM 实现（OpenAI、Azure、Ollama、DeepSeek 等）均继承此接口，保证可插拔。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# 避免循环导入：仅类型时用 TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.settings import Settings


class BaseLLM(ABC):
    """LLM 抽象基类，统一 chat 接口。"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]]) -> str:
        """
        根据消息历史生成回复文本。

        Args:
            messages: 消息列表，每项通常含 "role"（"system"|"user"|"assistant"）与 "content"。

        Returns:
            助手回复的纯文本内容。
        """
        ...

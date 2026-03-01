"""
Transform 抽象基类（C5）：chunks in → transform → chunks out；失败降级不阻塞。
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from core.types import Chunk


class BaseTransform(ABC):
    """Chunk 变换抽象：规则/LLM 增强等，单 chunk 异常不影响其余。"""

    @abstractmethod
    def transform(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[Chunk]:
        """
        对 chunk 列表进行变换，返回新列表（可新对象、可更新 text/metadata）。

        Args:
            chunks: 输入 Chunk 列表。
            trace: 可选 TraceContext。

        Returns:
            变换后的 Chunk 列表；单条失败时可保留原文并标记 metadata。
        """
        ...

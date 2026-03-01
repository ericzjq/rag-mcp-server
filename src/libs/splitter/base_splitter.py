"""
Splitter 抽象基类。

所有切分策略实现（Recursive、Semantic、Fixed 等）均继承此接口。
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class BaseSplitter(ABC):
    """Splitter 抽象基类，统一 split_text 接口。"""

    @abstractmethod
    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
    ) -> List[str]:
        """
        将整段文本切分为若干片段。

        Args:
            text: 待切分的原文。
            trace: 可选追踪上下文（TraceContext，F 阶段实现），当前可传 None。

        Returns:
            切分后的字符串列表（每个元素为一个 chunk 的文本）。
        """
        ...

"""
Embedding 抽象基类。

所有 Embedding 实现（OpenAI、Azure、Ollama 等）均继承此接口，支持批量 embed。
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class BaseEmbedding(ABC):
    """Embedding 抽象基类，统一批量向量化接口。"""

    @abstractmethod
    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        """
        将文本列表编码为向量列表。

        Args:
            texts: 待编码的文本列表。
            trace: 可选追踪上下文（TraceContext，F 阶段实现），当前可传 None。

        Returns:
            与 texts 等长的向量列表，每项为浮点向量。
        """
        ...

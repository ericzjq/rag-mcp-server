"""
Loader 抽象基类（C3）：统一 load(path) -> Document 接口。
"""

from abc import ABC, abstractmethod
from pathlib import Path

from core.types import Document


class BaseLoader(ABC):
    """文档加载器抽象：根据路径加载并返回 Document。"""

    @abstractmethod
    def load(self, path: str) -> Document:
        """
        加载路径对应文档，返回 Document。

        Args:
            path: 文件路径（如 PDF 路径）。

        Returns:
            Document，metadata 至少含 source_path；若有图片则含 metadata.images 与占位符。
        """
        ...

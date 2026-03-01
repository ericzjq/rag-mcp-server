"""
Recursive Splitter：封装 LangChain RecursiveCharacterTextSplitter。

按段落/换行/空格递归切分，保持 Markdown 标题与代码块等结构尽量不被打断。
"""

from typing import Any, List, Optional

from core.settings import Settings

from libs.splitter.base_splitter import BaseSplitter


class RecursiveSplitter(BaseSplitter):
    """基于 LangChain RecursiveCharacterTextSplitter 的默认切分器。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chunk_size = settings.splitter.chunk_size
        self._chunk_overlap = settings.splitter.chunk_overlap
        self._splitter = None  # 延迟初始化以便测试可 mock

    def _get_splitter(self):
        if self._splitter is None:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
            except ImportError as e:
                raise RuntimeError(
                    "RecursiveSplitter 需要 langchain-text-splitters，请 pip install langchain-text-splitters"
                ) from e
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
        return self._splitter

    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
    ) -> List[str]:
        if not text or not text.strip():
            return []
        splitter = self._get_splitter()
        return splitter.split_text(text.strip())

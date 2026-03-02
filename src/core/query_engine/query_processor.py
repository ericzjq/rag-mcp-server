"""
QueryProcessor（D1）：关键词提取（规则/分词）+ 通用 filters 结构（可空实现）。
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List

# 简单英文停用词（可扩展）
_DEFAULT_STOP: set = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
}


def _tokenize(text: str) -> List[str]:
    """分词：非字母数字切分、小写，过滤空串。与 SparseEncoder 一致便于 BM25 查询。"""
    if not text or not text.strip():
        return []
    lowered = text.strip().lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    return [t for t in tokens if t]


@dataclass
class ProcessedQuery:
    """处理后的查询：关键词列表 + filters 字典。"""

    keywords: List[str]
    filters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"keywords": list(self.keywords), "filters": dict(self.filters)}


class QueryProcessor:
    """对用户 query 做关键词提取与 filters 解析；filters 当前可空实现，恒返回空 dict。"""

    def __init__(self, stop_words: Any = None) -> None:
        self._stop = set(stop_words) if stop_words is not None else _DEFAULT_STOP

    def process(self, query: str) -> ProcessedQuery:
        """
        提取关键词（去停用词）并解析 filters。

        Args:
            query: 用户查询字符串。

        Returns:
            ProcessedQuery(keywords=..., filters=...)；keywords 非空（当 query 有有效词时），filters 为 dict。
        """
        tokens = _tokenize(query)
        keywords = [t for t in tokens if t not in self._stop]
        # 若全部被停用词过滤则保留原 token 列表，保证非空（验收：keywords 非空）
        if not keywords and tokens:
            keywords = list(tokens)
        return ProcessedQuery(keywords=keywords, filters={})

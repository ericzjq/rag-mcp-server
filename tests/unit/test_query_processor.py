"""
QueryProcessor 单元测试（D1）：keywords 非空（有内容时）、filters 为 dict。
"""

import pytest

from core.query_engine.query_processor import ProcessedQuery, QueryProcessor, _tokenize


def test_process_returns_keywords_non_empty_when_query_has_content() -> None:
    """对含有效词的 query 输出 keywords 非空。"""
    proc = QueryProcessor()
    r = proc.process("hello world")
    assert isinstance(r, ProcessedQuery)
    assert r.keywords
    assert "hello" in r.keywords and "world" in r.keywords


def test_process_returns_filters_dict() -> None:
    """filters 恒为 dict（可空实现）。"""
    proc = QueryProcessor()
    r = proc.process("anything")
    assert isinstance(r.filters, dict)
    assert r.filters == {}


def test_process_stopwords_filtered() -> None:
    """停用词被过滤，剩余词在 keywords 中。"""
    proc = QueryProcessor()
    r = proc.process("the cat is on the mat")
    assert "cat" in r.keywords and "mat" in r.keywords
    assert "the" not in r.keywords and "is" not in r.keywords


def test_process_all_stopwords_fallback_to_tokens() -> None:
    """全部为停用词时保留 token 列表使 keywords 非空。"""
    proc = QueryProcessor()
    r = proc.process("the the the")
    assert r.keywords == ["the", "the", "the"]


def test_process_empty_query() -> None:
    """空 query 得到空 keywords、空 filters。"""
    proc = QueryProcessor()
    r = proc.process("")
    assert r.keywords == []
    assert r.filters == {}
    r2 = proc.process("   ")
    assert r2.keywords == []


def test_tokenize_lowercase_alnum() -> None:
    """分词与 SparseEncoder 一致：小写、仅字母数字。"""
    assert _tokenize("Hello World") == ["hello", "world"]
    assert _tokenize("a1b2") == ["a1b2"]


def test_processed_query_to_dict() -> None:
    """ProcessedQuery.to_dict 可序列化。"""
    r = ProcessedQuery(keywords=["a", "b"], filters={})
    d = r.to_dict()
    assert d["keywords"] == ["a", "b"]
    assert d["filters"] == {}

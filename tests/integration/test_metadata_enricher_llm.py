"""
MetadataEnricher 集成测试（C6）：真实 LLM 配置下的连通性与效果验证。

运行方式（需先补全 config/settings.yaml 中的 LLM 配置及对应环境变量）：
  pytest tests/integration/test_metadata_enricher_llm.py -v -s -m integration

无配置或缺少 API key 时会 skip，不报错。
"""

import os

import pytest

from core.settings import load_settings
from core.types import Chunk
from ingestion.transform.metadata_enricher import MetadataEnricher


def _has_llm_config(settings) -> bool:
    """判断是否具备可用的 LLM 配置（provider + 至少 api_key 或 base_url）。"""
    llm = getattr(settings, "llm", None)
    if llm is None:
        return False
    provider = (getattr(llm, "provider", None) or "").strip().lower()
    if not provider:
        return False
    if provider == "ollama":
        return bool(getattr(llm, "base_url", None) or os.environ.get("OLLAMA_BASE_URL"))
    if provider in ("openai", "azure", "deepseek"):
        return bool(
            getattr(llm, "api_key", None)
            or getattr(llm, "azure_endpoint", None)
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("AZURE_OPENAI_API_KEY")
        )
    return bool(getattr(llm, "api_key", None))


@pytest.mark.integration
def test_metadata_enricher_real_llm_connectivity_and_effect() -> None:
    """
    在有真实 LLM 配置下验证：
    1. 连通性：调用不抛异常，能拿到响应。
    2. 效果：enriched_by 为 llm 时，title/summary/tags 非空且语义合理。
    """
    config_path = os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml")
    if not os.path.exists(config_path):
        pytest.skip(f"Config not found: {config_path}")

    settings = load_settings(config_path)
    if not _has_llm_config(settings):
        pytest.skip("LLM not configured (llm.api_key / base_url or env OPENAI_API_KEY etc.)")

    enricher = MetadataEnricher(settings, use_llm=True)
    chunk = Chunk(
        id="int_c1",
        text="Python is a high-level programming language. It emphasizes code readability and supports multiple programming paradigms.",
        metadata={"source_path": "sample.txt"},
        source_ref="doc1",
    )
    out = enricher.transform([chunk], trace=None)

    assert len(out) == 1, "应返回 1 个 chunk"
    m = out[0].metadata

    # 连通性：必有 title / summary / tags（规则兜底或 LLM）
    assert "title" in m and m["title"], "metadata 应含非空 title"
    assert "summary" in m and m["summary"], "metadata 应含非空 summary"
    assert "tags" in m and isinstance(m["tags"], list), "metadata 应含 tags 列表"

    # 效果：若为 LLM 增强，则内容不应是纯占位
    if m.get("enriched_by") == "llm":
        assert m["title"] not in ("(no title)", ""), "LLM 模式下 title 应有实质内容"
        assert m["summary"] not in ("(no summary)", ""), "LLM 模式下 summary 应有实质内容"
        assert len(m["tags"]) > 0, "LLM 模式下 tags 非空"
    else:
        assert m.get("enrichment_fallback"), "未走 LLM 时应标记 enrichment_fallback 原因"

    # 输出 LLM 返回的 title / summary / tags（运行 pytest -s 可见）
    print("\n--- MetadataEnricher 测试结果 (LLM 返回) ---")
    print("enriched_by:", m.get("enriched_by"))
    print("title:", m.get("title"))
    print("summary:", m.get("summary"))
    print("tags:", m.get("tags"))
    print("---")

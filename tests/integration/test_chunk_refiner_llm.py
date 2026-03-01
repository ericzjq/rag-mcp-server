"""
ChunkRefiner 集成测试（C5）：真实 LLM 调用验证；需配置 settings + API key，标记 integration。
"""

import os

import pytest

from core.settings import load_settings
from core.types import Chunk
from ingestion.transform.chunk_refiner import ChunkRefiner


@pytest.mark.integration
def test_chunk_refiner_real_llm_refines() -> None:
    """真实 LLM 调用：需 config/settings.yaml 与 OPENAI_API_KEY（或对应 provider 环境变量）。"""
    config_path = os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml")
    if not os.path.exists(config_path):
        pytest.skip(f"Config not found: {config_path}")
    settings = load_settings(config_path)
    refiner = ChunkRefiner(settings, use_llm=True)
    chunks = [Chunk(id="c1", text="  Noisy   text   with   spaces.  ", metadata={}, source_ref="d1")]
    out = refiner.transform(chunks, trace=None)
    assert len(out) == 1
    assert out[0].metadata.get("refined_by") in ("llm", "rule")
    if out[0].metadata.get("refined_by") == "llm":
        assert out[0].text.strip()
    else:
        assert out[0].metadata.get("refinement_fallback")

"""
配置加载与校验单元测试。

对应 DEV_SPEC A3 验收：load_settings 成功加载、缺字段时抛出可读错误（含字段路径）。
"""

import tempfile
from pathlib import Path

import pytest

from core.settings import (
    Settings,
    load_settings,
    validate_settings,
)


def test_load_settings_from_default_path() -> None:
    """main.py 启动时能成功加载 config/settings.yaml 并拿到 Settings 对象。"""
    path = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    if not path.exists():
        pytest.skip("config/settings.yaml not found (copy from settings.yaml.example)")
    settings = load_settings(str(path))
    assert isinstance(settings, Settings)
    assert settings.llm.provider and settings.llm.model
    assert settings.embedding.provider and settings.embedding.model
    assert settings.vector_store.provider == "chroma"
    assert settings.observability.log_level
    assert settings.splitter.provider and settings.splitter.chunk_size > 0


def test_validate_settings_accepts_valid_settings() -> None:
    """validate_settings 对合法 Settings 不抛错。"""
    path = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    if not path.exists():
        pytest.skip("config/settings.yaml not found")
    settings = load_settings(str(path))
    validate_settings(settings)  # no raise


def test_load_settings_missing_top_level_raises_readable() -> None:
    """缺失顶层节时抛出 ValueError，错误信息包含字段路径。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("llm:\n  provider: openai\n  model: gpt-4\n")
        # 缺少 embedding, vector_store, ...
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError) as exc_info:
            load_settings(path)
        msg = str(exc_info.value)
        assert "Missing required field:" in msg
        assert "embedding" in msg or "provider" in msg or "vector_store" in msg
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_settings_missing_embedding_provider_raises_readable() -> None:
    """删除 embedding.provider 时抛出可读错误，明确指出缺的是 embedding.provider。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
llm:
  provider: openai
  model: gpt-4o-mini
embedding:
  model: text-embedding-3-small
vector_store:
  provider: chroma
  persist_directory: data/chroma
retrieval:
  top_k: 10
  rerank_top_m: 20
rerank:
  provider: none
splitter:
  provider: recursive
  chunk_size: 512
  chunk_overlap: 50
evaluation:
  provider: ragas
observability:
  log_level: INFO
  traces_path: logs/traces.jsonl
""")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError) as exc_info:
            load_settings(path)
        msg = str(exc_info.value)
        assert "embedding.provider" in msg
        assert "Missing required field:" in msg
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_settings_nonexistent_file_raises() -> None:
    """文件不存在时抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_settings("/nonexistent/settings.yaml")
    assert "nonexistent" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

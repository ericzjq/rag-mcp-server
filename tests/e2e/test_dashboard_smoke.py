"""
E2E：Dashboard 冒烟测试（I2）。使用 Streamlit AppTest 验证各页面均可加载、不抛异常。
因 AppTest.from_function 不会注入 streamlit，改用 from_string 注入含 import streamlit 的完整脚本。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _minimal_config_yaml(tmp_path: Path) -> str:
    """生成最小可解析的 settings.yaml 内容，供 Dashboard 页面加载。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "settings.yaml"
    config_path.write_text(
        """
llm: { provider: openai, model: gpt-4o-mini }
embedding: { provider: openai, model: text-embedding-3-small }
vector_store: { provider: chroma, persist_directory: data/chroma }
retrieval: { top_k: 10, rerank_top_m: 20 }
rerank: { provider: none }
splitter: { provider: recursive, chunk_size: 256, chunk_overlap: 32 }
evaluation: { provider: ragas }
observability: { log_level: INFO, traces_path: logs/traces.jsonl }
""",
        encoding="utf-8",
    )
    return str(config_path)


def _run_page_smoke(tmp_path: Path, module_path: str, expected_title: str) -> None:
    """用 AppTest.from_string 执行单页脚本（含 import streamlit），验证标题存在且无异常。"""
    config_path = _minimal_config_yaml(tmp_path)
    work_dir = str(tmp_path)
    # 注入完整脚本，确保 streamlit 在页面 run() 执行时可用；用 repr 避免路径中的引号/反斜杠破坏脚本
    script = f"""
import streamlit as st
from {module_path} import run
run(config_path={repr(config_path)}, work_dir={repr(work_dir)})
"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script.strip())
    at.run(timeout=10)
    titles = at.title
    assert len(titles) >= 1, "页面应至少有一个 title"
    assert titles[0].value == expected_title, "页面标题应为 %s" % expected_title


@pytest.mark.e2e
def test_dashboard_overview_page_loads(tmp_path: Path) -> None:
    """系统总览页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.overview", "系统总览")


@pytest.mark.e2e
def test_dashboard_data_browser_page_loads(tmp_path: Path) -> None:
    """数据浏览器页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.data_browser", "数据浏览器")


@pytest.mark.e2e
def test_dashboard_ingestion_manager_page_loads(tmp_path: Path) -> None:
    """Ingestion 管理页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.ingestion_manager", "Ingestion 管理")


@pytest.mark.e2e
def test_dashboard_ingestion_traces_page_loads(tmp_path: Path) -> None:
    """Ingestion 追踪页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.ingestion_traces", "Ingestion 追踪")


@pytest.mark.e2e
def test_dashboard_query_traces_page_loads(tmp_path: Path) -> None:
    """Query 追踪页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.query_traces", "Query 追踪")


@pytest.mark.e2e
def test_dashboard_online_search_page_loads(tmp_path: Path) -> None:
    """在线检索页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.online_search", "在线检索")


@pytest.mark.e2e
def test_dashboard_ragas_results_page_loads(tmp_path: Path) -> None:
    """RAGAS 评估结果页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.ragas_results", "RAGAS 评估结果")


@pytest.mark.e2e
def test_dashboard_evaluation_panel_page_loads(tmp_path: Path) -> None:
    """评估面板页可加载、不抛异常。"""
    _run_page_smoke(tmp_path, "observability.dashboard.pages.evaluation_panel", "评估")

"""
Dashboard 入口（G1）：多页面导航架构，总览页 + 占位页。
"""

import os
import sys
from pathlib import Path

# 确保 src 在 path 中（core / libs / observability），项目根为工作目录以便 config/settings.yaml
_APP_DIR = Path(__file__).resolve().parent
_ROOT = _APP_DIR.parent.parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

import streamlit as st

from observability.dashboard.pages.overview import run as overview_run
from observability.dashboard.pages.data_browser import run as data_browser_run
from observability.dashboard.pages.ingestion_manager import run as ingestion_manager_run
from observability.dashboard.pages.ingestion_traces import run as ingestion_traces_run
from observability.dashboard.pages.query_traces import run as query_traces_run
from observability.dashboard.pages.online_search import run as online_search_run
from observability.dashboard.pages.ragas_results import run as ragas_results_run
from observability.dashboard.pages.evaluation_panel import run as evaluation_panel_run


def _placeholder(title: str):
    def _fn() -> None:
        st.title(title)
        st.info("该页面尚未实现，敬请期待。")
    return _fn


def main() -> None:
    pages = [
        st.Page(overview_run, title="系统总览", url_path="overview", default=True),
        st.Page(data_browser_run, title="数据浏览器", url_path="data-browser"),
        st.Page(ingestion_manager_run, title="Ingestion 管理", url_path="ingestion-manager"),
        st.Page(ingestion_traces_run, title="Ingestion 追踪", url_path="ingestion-traces"),
        st.Page(query_traces_run, title="Query 追踪", url_path="query-traces"),
        st.Page(online_search_run, title="在线检索", url_path="online-search"),
        st.Page(ragas_results_run, title="RAGAS 评估结果", url_path="ragas-results"),
        st.Page(evaluation_panel_run, title="评估", url_path="evaluation"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()

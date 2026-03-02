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


def _placeholder(title: str):
    def _fn() -> None:
        st.title(title)
        st.info("该页面尚未实现，敬请期待。")
    return _fn


def main() -> None:
    pages = [
        st.Page(overview_run, title="系统总览", default=True),
        st.Page(_placeholder("数据浏览器"), title="数据浏览器"),
        st.Page(_placeholder("Ingestion 管理"), title="Ingestion 管理"),
        st.Page(_placeholder("Ingestion 追踪"), title="Ingestion 追踪"),
        st.Page(_placeholder("Query 追踪"), title="Query 追踪"),
        st.Page(_placeholder("评估"), title="评估"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()

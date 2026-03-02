"""
系统总览页（G1）：展示组件配置与数据统计。
"""

import streamlit as st

from observability.dashboard.services.config_service import ConfigService


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("系统总览")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    if settings is None:
        st.warning("未找到配置文件（config/settings.yaml 或 MCP_CONFIG_PATH），仅显示占位。")
        return

    # 数据统计（Chroma）
    try:
        from libs.vector_store.chroma_store import ChromaStore
        store = ChromaStore(settings)
        stats = store.get_collection_stats()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("向量条数", stats.get("count", 0))
    except Exception as e:
        st.warning("无法加载向量库统计: %s" % e)

    st.divider()
    st.subheader("组件配置")
    cards = config.get_component_cards()
    for card in cards:
        with st.expander(card["title"], expanded=True):
            for k, v in card["items"]:
                st.text("%s: %s" % (k, v))

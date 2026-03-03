"""
在线检索页面（G7）：输入 query 发起检索，展示召回结果（Top-K、分数、可展开详情）。
"""

import os
import streamlit as st

from core.query_engine.hybrid_search import HybridSearch
from core.query_engine.reranker import Reranker

from observability.dashboard.services.config_service import ConfigService


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("在线检索")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    if settings is None:
        st.warning("未找到配置文件（config/settings.yaml），无法执行检索。")
        return

    query = st.text_input("输入查询（Query）", value="", key="online_search_query", placeholder="例如：张家琪是谁")
    col_topk, col_coll = st.columns(2)
    with col_topk:
        top_k = st.number_input("返回条数 (top_k)", min_value=1, max_value=50, value=10, key="online_search_topk")
    with col_coll:
        collection = st.text_input("集合（可选，留空为全部）", value="", key="online_search_collection")

    if st.button("检索", key="online_search_run"):
        if not (query or "").strip():
            st.warning("请输入查询文本。")
        else:
            try:
                hybrid = HybridSearch(settings)
                reranker = Reranker(settings)
                filters = {"collection": collection.strip()} if collection.strip() else None
                results = hybrid.search(query.strip(), top_k=top_k, filters=filters)
                if results:
                    results = reranker.rerank(query.strip(), results)
                if not results:
                    st.info("未找到相关文档。请先执行 ingest 摄取数据或调整查询。")
                else:
                    st.success("共召回 %d 条" % len(results))
                    for i, r in enumerate(results, 1):
                        title = "Chunk %d | score=%.4f" % (i, r.score or 0)
                        with st.expander(title):
                            st.caption("chunk_id: %s" % (r.chunk_id or "-"))
                            if r.metadata:
                                st.caption("metadata: %s" % r.metadata)
                            text = (r.text or "").strip()
                            if len(text) > 800:
                                st.text_area("内容", value=text, height=120, key="online_search_%s" % (r.chunk_id or i), disabled=True)
                            else:
                                st.text(text)
            except Exception as e:
                st.error("检索失败: %s" % e)

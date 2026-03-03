"""
数据浏览器页面（G3）：文档列表、集合筛选、Chunk 详情、关联图片预览。
"""

import streamlit as st

from observability.dashboard.services.data_service import DataService


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("数据浏览器")
    data = DataService(config_path=config_path, work_dir=work_dir)
    collections = data.list_collections()
    doc_list = data.list_documents(collection=None)
    if not doc_list:
        st.info("暂无已摄入文档。请先在 Ingestion 管理页面上传并摄取文档。")
        return

    # 集合筛选
    filter_options = ["全部"] + collections
    selected = st.selectbox("按集合筛选", filter_options, index=0)
    collection_filter = None if selected == "全部" else selected
    if collection_filter is not None:
        doc_list = data.list_documents(collection=collection_filter)
        if not doc_list:
            st.info("该集合下暂无文档。")
            return

    if "data_browser_detail_id" not in st.session_state:
        st.session_state["data_browser_detail_id"] = None
    st.caption("共 %d 个文档" % len(doc_list))
    for info in doc_list:
        with st.expander("%s（%d chunks, %d 图）" % (info.source_path, info.chunk_count, info.image_count)):
            st.text("路径: %s" % info.source_path)
            st.text("doc_id: %s" % info.doc_id)
            if st.button("查看详情", key="detail_%s" % info.doc_id):
                st.session_state["data_browser_detail_id"] = info.doc_id
                st.rerun()
            if st.session_state.get("data_browser_detail_id") == info.doc_id:
                if st.button("← 返回列表", key="back_%s" % info.doc_id):
                    st.session_state["data_browser_detail_id"] = None
                    st.rerun()
                detail = data.get_document_detail(info.doc_id)
                if detail is None:
                    st.warning("无法加载详情")
                else:
                    st.subheader("Chunks")
                    for i, ch in enumerate(detail.chunks):
                        cid = ch.get("id", "")
                        with st.expander("Chunk %s" % (cid or i)):
                            st.caption("chunk_id（用于 golden test set 的 expected_chunk_ids）：%s" % (cid or "-"))
                            st.text_area("内容", value=ch.get("text", ""), height=120, disabled=True, key="chunk_%s_%s" % (info.doc_id, i))
                            meta = ch.get("metadata") or {}
                            if meta:
                                st.json(meta)
                    st.subheader("关联图片")
                    for j, img in enumerate(detail.images):
                        fp = img.get("file_path")
                        if fp and __import__("os").path.isfile(fp):
                            try:
                                from PIL import Image
                                st.image(Image.open(fp), caption=img.get("image_id", ""), use_container_width=True)
                            except Exception:
                                st.text("图片: %s" % img.get("image_id", fp))
                        else:
                            st.text("图片: %s (文件不存在)" % img.get("image_id", "-"))

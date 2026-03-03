"""
Ingestion 管理页面（G4）：文件上传触发摄取、实时进度展示、文档删除。
"""

import os
import tempfile
import traceback
import streamlit as st

from ingestion.pipeline import IngestionPipeline
from libs.loader.file_integrity import SQLiteIntegrityChecker

from observability.dashboard.services.config_service import ConfigService
from observability.dashboard.services.data_service import DataService
from ingestion.storage.image_storage import ImageStorage


DEFAULT_BM25_INDEX_DIR = "data/db/bm25"
DEFAULT_INGESTION_DB = "data/db/ingestion_history.db"
DEFAULT_IMAGE_DB = "data/db/image_index.db"
DEFAULT_IMAGES_BASE = "data/images"


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("Ingestion 管理")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    if settings is None:
        st.warning("未找到配置文件（config/settings.yaml），无法执行摄取。")
        return

    wd = work_dir or config._work_dir or os.getcwd()
    ingestion_db = os.path.join(wd, DEFAULT_INGESTION_DB)
    image_db = os.path.join(wd, DEFAULT_IMAGE_DB)
    images_base = os.path.join(wd, DEFAULT_IMAGES_BASE)
    bm25_dir = os.path.join(wd, DEFAULT_BM25_INDEX_DIR)

    # ---------- 上传与摄取 ----------
    st.subheader("上传并摄取")
    data = DataService(config_path=config_path, work_dir=work_dir)
    collections = data.list_collections()
    coll_options = ["（默认）"] + collections
    uploaded = st.file_uploader("选择 PDF 文件", type=["pdf"], key="ingestion_upload")
    col_coll, col_force = st.columns(2)
    with col_coll:
        coll_choice = st.selectbox(
            "集合（用于图片登记）",
            options=coll_options,
            index=0,
            key="ingestion_collection",
        )
        collection_name = "" if coll_choice == "（默认）" else coll_choice
    with col_force:
        force = st.checkbox("强制重新摄取（跳过已存在检查）", value=False, key="ingestion_force")

    if st.button("开始摄取", key="ingestion_run"):
        if uploaded is None:
            st.warning("请先选择要上传的 PDF 文件。")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                progress_bar = st.progress(0.0, text="准备中…")
                stage_label = st.empty()
                STAGES = ["load", "split", "transform", "embed", "upsert"]

                def on_progress(stage_name: str, current: int, total: int) -> None:
                    if stage_name in STAGES:
                        idx = STAGES.index(stage_name)
                        # 阶段完成：current==total；否则为阶段进行中（如 transform 0/225）
                        if total > 0 and current == total:
                            progress_bar.progress((idx + 1) / len(STAGES), text="%s 完成" % stage_name)
                        elif total > 0 and current == 0:
                            progress_bar.progress((idx + 0.5) / len(STAGES), text="%s 进行中…" % stage_name)
                    if total > 0:
                        stage_label.caption("当前：%s %d/%d" % (stage_name, current, total))
                    else:
                        stage_label.caption("当前：%s" % stage_name)

                integrity = SQLiteIntegrityChecker(db_path=ingestion_db)
                image_storage = ImageStorage(db_path=image_db, images_base=images_base)
                pipeline = IngestionPipeline(
                    settings,
                    integrity_checker=integrity,
                    image_storage=image_storage,
                    bm25_index_dir=bm25_dir,
                )
                result = pipeline.run(
                    tmp_path,
                    collection=collection_name or "",
                    force=force,
                    on_progress=on_progress,
                )
                if result.get("skipped"):
                    st.info("已跳过：该文件此前已成功摄取，未做变更。")
                else:
                    st.success(
                        "摄取完成：document_id=%s, chunks=%s, records=%s"
                        % (
                            result.get("document_id", ""),
                            result.get("chunks_count", 0),
                            result.get("records_count", 0),
                        )
                    )
            except Exception as e:
                st.error("摄取失败: %s" % e)
                with st.expander("查看详细错误（便于排查 transform/embed 超时或 API 异常）"):
                    st.code(traceback.format_exc(), language=None)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            st.rerun()

    st.divider()
    # ---------- 已摄入文档列表与删除 ----------
    st.subheader("已摄入文档")
    doc_list = data.list_documents(collection=None)
    if not doc_list:
        st.info("暂无已摄入文档。请在上方上传 PDF 并执行摄取。")
        return

    st.caption("共 %d 个文档" % len(doc_list))
    for info in doc_list:
        with st.expander("%s（%d chunks, %d 图）" % (info.source_path, info.chunk_count, info.image_count)):
            st.text("路径: %s" % info.source_path)
            st.text("doc_id: %s" % info.doc_id)
            if st.button("删除该文档", key="del_%s" % info.doc_id, type="secondary"):
                res = data.delete_document(info.source_path, collection="")
                if res is None:
                    st.error("删除失败（无法连接存储）。")
                else:
                    st.success(
                        "已删除：Chroma %d 条、BM25 已移除、图片 %d 张、integrity 已移除。"
                        % (res.chroma_deleted, res.images_deleted)
                    )
                st.rerun()
